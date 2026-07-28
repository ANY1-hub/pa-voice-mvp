import { api } from "./auth.js";
import { playBase64Audio } from "./audio.js";

const chatContainer = () => document.getElementById("chatContainer");
const statusLine = () => document.getElementById("statusLine");

export function appendMessage(role, text) {
    const el = document.createElement("div");
    el.className = `msg ${role}`;

    const roleLabel = document.createElement("div");
    roleLabel.className = "msg-role";
    roleLabel.textContent = role === "user" ? "You" : "J.A.R.V.I.S.";

    const body = document.createElement("div");
    body.className = "msg-body";
    body.textContent = text;

    el.appendChild(roleLabel);
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

export async function sendText(text) {
    setStatus("Processing…");
    const res = await api("/api/v1/chat/text", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
    }

    const data = await res.json();
    appendMessage("user", data.transcript);
    appendMessage("jarvis", data.response);
    playBase64Audio(data.audio_base64);
    setStatus("");
}

export async function sendVoice(blob) {
    setStatus("Transcribing & thinking…");
    const form = new FormData();
    form.append("audio", blob, "recording.wav");

    const res = await api("/api/v1/chat/voice", {
        method: "POST",
        body: form,
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || `Error ${res.status}`);
    }

    const data = await res.json();
    appendMessage("user", data.transcript);
    appendMessage("jarvis", data.response);
    playBase64Audio(data.audio_base64);
    setStatus("");
}
