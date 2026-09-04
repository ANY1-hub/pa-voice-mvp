import { getStoredUser } from "./auth.js";
import { t } from "./i18n.js";

function userScope() {
    const user = getStoredUser();
    return user.id || user.email || "anon";
}

function storageKey() {
    return `jarvis_sittings_${userScope()}`;
}

function currentKey() {
    return `jarvis_current_sitting_${userScope()}`;
}

function loadAll() {
    try {
        const raw = localStorage.getItem(storageKey());
        const parsed = JSON.parse(raw || "[]");
        return Array.isArray(parsed) ? parsed : [];
    } catch {
        return [];
    }
}

function saveAll(sittings) {
    localStorage.setItem(storageKey(), JSON.stringify(sittings));
}

export function getCurrentSittingId() {
    return localStorage.getItem(currentKey());
}

export function listSittings() {
    return loadAll().sort((a, b) => (b.updatedAt || "").localeCompare(a.updatedAt || ""));
}

export function getSitting(id) {
    return loadAll().find((item) => item.id === id) || null;
}

function upsert(sitting) {
    const all = loadAll().filter((item) => item.id !== sitting.id);
    all.push(sitting);
    saveAll(all);
}

export function ensureCurrentSitting() {
    let id = getCurrentSittingId();
    const existing = id ? getSitting(id) : null;
    if (existing) return existing;
    const sitting = {
        id: crypto.randomUUID(),
        title: t("newChat"),
        updatedAt: new Date().toISOString(),
        messages: [],
    };
    upsert(sitting);
    localStorage.setItem(currentKey(), sitting.id);
    return sitting;
}

export function recordMessage(role, text, isoUtc) {
    const sitting = ensureCurrentSitting();
    sitting.messages.push({
        role,
        text,
        utc: isoUtc || new Date().toISOString(),
    });
    if (role === "user" && sitting.messages.filter((m) => m.role === "user").length === 1) {
        sitting.title = text.trim().slice(0, 48) || t("newChat");
    }
    if (role === "jarvis") {
        const prev = sitting.messages[sitting.messages.length - 2];
        if (prev && prev.role === "user" && !prev.versions) {
            prev.versions = [{ user: prev.text, assistant: text, utc: isoUtc || prev.utc }];
            prev.versionIndex = 0;
        }
    }
    sitting.updatedAt = new Date().toISOString();
    upsert(sitting);
    return sitting;
}

function lastUserIndex(messages) {
    for (let i = messages.length - 1; i >= 0; i -= 1) {
        if (messages[i].role === "user") return i;
    }
    return -1;
}

export function lastUserTurnIsEditable(sitting) {
    const current = sitting || getSitting(getCurrentSittingId());
    if (!current) return false;
    const idx = lastUserIndex(current.messages || []);
    if (idx < 0) return false;
    return !(current.messages.slice(idx + 1).some((m) => m.role === "user"));
}

export function replaceLastTurn(userText, assistantText, utc) {
    const sitting = ensureCurrentSitting();
    if (!lastUserTurnIsEditable(sitting)) return null;
    const idx = lastUserIndex(sitting.messages);
    const userMsg = sitting.messages[idx];
    const next = sitting.messages[idx + 1];
    const jarvisMsg = next && next.role === "jarvis" ? next : null;
    if (!userMsg.versions) {
        userMsg.versions = [
            {
                user: userMsg.text,
                assistant: jarvisMsg ? jarvisMsg.text : "",
                utc: userMsg.utc,
            },
        ];
    }
    userMsg.versions.push({
        user: userText,
        assistant: assistantText,
        utc,
    });
    userMsg.versionIndex = userMsg.versions.length - 1;
    userMsg.text = userText;
    userMsg.utc = utc;
    if (jarvisMsg) {
        jarvisMsg.text = assistantText;
        jarvisMsg.utc = utc;
    } else {
        sitting.messages.push({ role: "jarvis", text: assistantText, utc });
    }
    sitting.updatedAt = new Date().toISOString();
    upsert(sitting);
    return sitting;
}

export function setDisplayedVersion(versionIndex) {
    const sitting = ensureCurrentSitting();
    if (!lastUserTurnIsEditable(sitting)) return null;
    const idx = lastUserIndex(sitting.messages);
    const userMsg = sitting.messages[idx];
    if (!userMsg.versions || !userMsg.versions[versionIndex]) return sitting;
    const version = userMsg.versions[versionIndex];
    userMsg.versionIndex = versionIndex;
    userMsg.text = version.user;
    userMsg.utc = version.utc;
    const next = sitting.messages[idx + 1];
    if (next && next.role === "jarvis") {
        next.text = version.assistant;
        next.utc = version.utc;
    }
    sitting.updatedAt = new Date().toISOString();
    upsert(sitting);
    return sitting;
}

export function deleteSitting(id) {
    const remaining = loadAll().filter((item) => item.id !== id);
    saveAll(remaining);
    if (getCurrentSittingId() !== id) {
        return remaining.sort((a, b) => (b.updatedAt || "").localeCompare(a.updatedAt || ""))[0] || null;
    }
    if (!remaining.length) {
        return startNewSitting();
    }
    const next = remaining.sort((a, b) => (b.updatedAt || "").localeCompare(a.updatedAt || ""))[0];
    localStorage.setItem(currentKey(), next.id);
    return next;
}

export function startNewSitting() {
    const sitting = {
        id: crypto.randomUUID(),
        title: t("newChat"),
        updatedAt: new Date().toISOString(),
        messages: [],
    };
    upsert(sitting);
    localStorage.setItem(currentKey(), sitting.id);
    return sitting;
}

export function switchSitting(id) {
    const sitting = getSitting(id);
    if (!sitting) return null;
    localStorage.setItem(currentKey(), id);
    return sitting;
}
