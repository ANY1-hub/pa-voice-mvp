import { api } from "./auth.js";
import { playBase64Audio } from "./audio.js";
import { getChatLang, t } from "./i18n.js";
import {
    getCurrentSittingId,
    getSitting,
    lastUserTurnIsEditable,
    recordMessage,
    replaceLastTurn,
    setDisplayedVersion,
} from "./sittings.js";

function chatLanguageParam() {
    const lang = getChatLang();
    return lang === "auto" ? null : lang;
}

const chatContainer = () => document.getElementById("chatContainer");
const statusLine = () => document.getElementById("statusLine");

let lastLocalDayKey = null;

function localDayKey(date) {
    return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`;
}

function formatLocalTime(date) {
    return date.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

function formatLocalDate(date) {
    return date.toLocaleDateString(undefined, {
        weekday: "long",
        year: "numeric",
        month: "long",
        day: "numeric",
    });
}

function maybeAppendDateSeparator(when) {
    const key = localDayKey(when);
    if (lastLocalDayKey === key) return;
    lastLocalDayKey = key;
    const sep = document.createElement("div");
    sep.className = "chat-date-sep";
    sep.textContent = formatLocalDate(when);
    chatContainer().appendChild(sep);
}

export function resetChatTimestamps() {
    lastLocalDayKey = null;
}

export function syncEmptyState() {
    const chat = chatContainer();
    const column = document.querySelector(".chat-column");
    if (!chat || !column) return;
    column.classList.toggle("is-empty", !chat.querySelector(".msg"));
}

export function appendMessage(role, text, isoUtc, options = {}) {
    const persist = options.persist !== false;
    const when = isoUtc ? new Date(isoUtc) : new Date();
    maybeAppendDateSeparator(when);

    const el = document.createElement("div");
    el.className = `msg ${role}`;
    el.dataset.utc = when.toISOString();

    const meta = document.createElement("div");
    meta.className = "msg-role";

    const name = document.createElement("span");
    name.textContent = role === "user" ? t("you") : t("jarvis");

    const time = document.createElement("time");
    time.className = "msg-time";
    time.dateTime = when.toISOString();
    time.textContent = formatLocalTime(when);

    meta.appendChild(name);
    meta.appendChild(time);

    const body = document.createElement("div");
    body.className = "msg-body";
    body.textContent = text;

    el.appendChild(meta);
    el.appendChild(body);
    chatContainer().appendChild(el);
    chatContainer().scrollTop = chatContainer().scrollHeight;
    syncEmptyState();
    if (persist) {
        recordMessage(role, text, el.dataset.utc);
        window.dispatchEvent(new Event("jarvis:sitting-updated"));
    }
    refreshTurnChrome();
}

function lastUserBubble() {
    const nodes = [...chatContainer().querySelectorAll(".msg.user")];
    return nodes.length ? nodes[nodes.length - 1] : null;
}

export function refreshTurnChrome() {
    chatContainer()?.querySelectorAll(".msg-toolbar").forEach((el) => el.remove());
    const sitting = getSitting(getCurrentSittingId());
    if (!sitting || !lastUserTurnIsEditable(sitting)) return;
    const userEl = lastUserBubble();
    if (!userEl) return;
    const userMsg = [...sitting.messages].reverse().find((m) => m.role === "user");
    const versions = userMsg?.versions || [];
    const index = userMsg?.versionIndex || 0;
    const bar = document.createElement("div");
    bar.className = "msg-toolbar";
    if (versions.length > 1) {
        const prev = document.createElement("button");
        prev.type = "button";
        prev.className = "msg-version-btn";
        prev.textContent = "‹";
        prev.disabled = index <= 0;
        prev.addEventListener("click", () => {
            setDisplayedVersion(index - 1);
            window.dispatchEvent(new Event("jarvis:sitting-repaint"));
        });
        const label = document.createElement("span");
        label.className = "msg-version-label";
        label.textContent = `${index + 1}/${versions.length}`;
        const next = document.createElement("button");
        next.type = "button";
        next.className = "msg-version-btn";
        next.textContent = "›";
        next.disabled = index >= versions.length - 1;
        next.addEventListener("click", () => {
            setDisplayedVersion(index + 1);
            window.dispatchEvent(new Event("jarvis:sitting-repaint"));
        });
        bar.appendChild(prev);
        bar.appendChild(label);
        bar.appendChild(next);
    }
    const edit = document.createElement("button");
    edit.type = "button";
    edit.className = "msg-edit";
    edit.title = t("editMessage");
    edit.textContent = "✎";
    edit.addEventListener("click", () => startEdit(userEl));
    bar.appendChild(edit);
    userEl.appendChild(bar);
}

function startEdit(userEl) {
    if (userEl.querySelector(".msg-edit-box")) return;
    const body = userEl.querySelector(".msg-body");
    const original = body.textContent;
    body.classList.add("hidden");
    userEl.querySelector(".msg-toolbar")?.classList.add("hidden");
    const box = document.createElement("div");
    box.className = "msg-edit-box";
    const area = document.createElement("textarea");
    area.value = original;
    const actions = document.createElement("div");
    actions.className = "msg-edit-actions";
    const cancel = document.createElement("button");
    cancel.type = "button";
    cancel.className = "btn-ghost";
    cancel.textContent = t("cancelEdit");
    const save = document.createElement("button");
    save.type = "button";
    save.className = "btn-send";
    save.textContent = t("saveEdit");
    cancel.addEventListener("click", () => {
        box.remove();
        body.classList.remove("hidden");
        refreshTurnChrome();
    });
    save.addEventListener("click", async () => {
        const next = area.value.trim();
        if (!next || next === original) {
            cancel.click();
            return;
        }
        save.disabled = true;
        try {
            await sendText(next, { replaceLast: true });
        } catch (err) {
            setStatus(err.message || t("editFailed"), true);
            save.disabled = false;
        }
    });
    actions.appendChild(cancel);
    actions.appendChild(save);
    box.appendChild(area);
    box.appendChild(actions);
    userEl.appendChild(box);
    area.focus();
}

export function setStatus(msg, isError = false) {
    const el = statusLine();
    if (!msg) {
        el.classList.add("hidden");
        return;
    }
    el.textContent = msg;
    el.classList.toggle("error", isError);
    el.classList.remove("hidden");
}

function formatApiDetail(detail) {
    if (!detail) return "";
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
        return detail
            .map((item) => (item && item.msg) || JSON.stringify(item))
            .join("; ");
    }
    return String(detail);
}

export async function sendText(text, options = {}) {
    setStatus(t("processing"));
    const res = await api("/api/v1/chat/text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, language: chatLanguageParam() }),
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(formatApiDetail(err.detail) || `Error ${res.status}`);
    }

    const data = await res.json();
    const sentAt = new Date().toISOString();
    if (options.replaceLast) {
        replaceLastTurn(data.transcript, data.response, sentAt);
        window.dispatchEvent(new Event("jarvis:sitting-repaint"));
        window.dispatchEvent(new Event("jarvis:sitting-updated"));
    } else {
        appendMessage("user", data.transcript, sentAt);
        appendMessage("jarvis", data.response, sentAt);
    }
    playBase64Audio(data.audio_base64);
    setStatus("");
}

export async function sendVoice(blob) {
    setStatus(t("transcribing"));
    const form = new FormData();
    form.append("audio", blob, "recording.wav");
    const chatLang = chatLanguageParam();
    if (chatLang) form.append("language", chatLang);

    const res = await api("/api/v1/chat/voice", {
        method: "POST",
        body: form,
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(formatApiDetail(err.detail) || `Error ${res.status}`);
    }

    const data = await res.json();
    const sentAt = new Date().toISOString();
    appendMessage("user", data.transcript, sentAt);
    appendMessage("jarvis", data.response, sentAt);
    playBase64Audio(data.audio_base64);
    setStatus("");
}
