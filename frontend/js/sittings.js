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
    sitting.updatedAt = new Date().toISOString();
    upsert(sitting);
    return sitting;
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
