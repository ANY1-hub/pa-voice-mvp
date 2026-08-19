import { api } from "./auth.js";
import { playBase64Audio } from "./audio.js";
import { t } from "./i18n.js";

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

export function appendMessage(role, text, isoUtc) {
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

export async function sendText(text) {
    setStatus(t("processing"));
    const res = await api("/api/v1/chat/text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
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

export async function sendVoice(blob) {
    setStatus(t("transcribing"));
    const form = new FormData();
    form.append("audio", blob, "recording.wav");

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
