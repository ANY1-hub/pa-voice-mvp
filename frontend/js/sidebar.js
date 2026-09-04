import { api, getStoredUser } from "./auth.js";
import { applyI18n, t } from "./i18n.js";
import {
    deleteSitting,
    ensureCurrentSitting,
    getCurrentSittingId,
    getSitting,
    listSittings,
    startNewSitting,
    switchSitting,
} from "./sittings.js";
import { appendMessage, resetChatTimestamps, syncEmptyState } from "./chat.js";

let mode = "chats";

function listEl() {
    return document.getElementById("sidebarList");
}

function setActiveButtons() {
    document.getElementById("notesBtn")?.classList.toggle("is-active", mode === "notes");
    document.getElementById("remindersBtn")?.classList.toggle("is-active", mode === "reminders");
    document.getElementById("chatsBtn")?.classList.toggle("is-active", mode === "chats");
}

function emptyItem(key) {
    const li = document.createElement("li");
    li.className = "sidebar-empty";
    li.textContent = t(key);
    return li;
}

function renderChats() {
    const ul = listEl();
    ul.innerHTML = "";
    const sittings = listSittings();
    const current = getCurrentSittingId();
    if (!sittings.length) {
        ul.appendChild(emptyItem("emptyChats"));
        return;
    }
    for (const sitting of sittings) {
        const li = document.createElement("li");
        const row = document.createElement("div");
        row.className = "sidebar-item-row";
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "sidebar-item" + (sitting.id === current ? " is-active" : "");
        btn.textContent = sitting.title || t("newChat");
        btn.addEventListener("click", () => {
            loadSitting(sitting.id);
            closeMobileSidebar();
        });
        const del = document.createElement("button");
        del.type = "button";
        del.className = "sidebar-item-menu";
        del.title = t("deleteChat");
        del.setAttribute("aria-label", t("deleteChat"));
        del.textContent = "⋮";
        del.addEventListener("click", (event) => {
            event.stopPropagation();
            removeChat(sitting.id);
        });
        row.appendChild(btn);
        row.appendChild(del);
        li.appendChild(row);
        ul.appendChild(li);
    }
}

function preview(text) {
    const line = (text || "").trim().replace(/\s+/g, " ");
    return line.length > 72 ? `${line.slice(0, 72)}…` : line;
}

async function renderNotes() {
    const ul = listEl();
    ul.innerHTML = "";
    const res = await api("/api/v1/notes");
    if (!res.ok) {
        ul.appendChild(emptyItem("emptyNotes"));
        return;
    }
    const data = await res.json();
    const notes = data.notes || [];
    if (!notes.length) {
        ul.appendChild(emptyItem("emptyNotes"));
        return;
    }
    for (const note of notes) {
        const li = document.createElement("li");
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "sidebar-item";
        const title = note.title || preview(note.content);
        btn.textContent = title;
        if (note.title && note.content) {
            const meta = document.createElement("span");
            meta.className = "sidebar-item-meta";
            meta.textContent = preview(note.content);
            btn.appendChild(meta);
        }
        li.appendChild(btn);
        ul.appendChild(li);
    }
}

async function renderReminders() {
    const ul = listEl();
    ul.innerHTML = "";
    const res = await api("/api/v1/reminders");
    if (!res.ok) {
        ul.appendChild(emptyItem("emptyReminders"));
        return;
    }
    const data = await res.json();
    const reminders = data.reminders || [];
    if (!reminders.length) {
        ul.appendChild(emptyItem("emptyReminders"));
        return;
    }
    for (const item of reminders) {
        const li = document.createElement("li");
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "sidebar-item";
        btn.textContent = preview(item.content);
        const meta = document.createElement("span");
        meta.className = "sidebar-item-meta";
        const due = item.due_at ? new Date(item.due_at).toLocaleString() : "";
        meta.textContent = [item.status, due].filter(Boolean).join(" · ");
        btn.appendChild(meta);
        li.appendChild(btn);
        ul.appendChild(li);
    }
}

export async function refreshSidebar() {
    if (!getStoredUser().id && !getStoredUser().email) return;
    setActiveButtons();
    if (mode === "notes") {
        await renderNotes();
        return;
    }
    if (mode === "reminders") {
        await renderReminders();
        return;
    }
    renderChats();
}

function paintSitting(sitting) {
    const chat = document.getElementById("chatContainer");
    chat.innerHTML = "";
    resetChatTimestamps();
    for (const msg of sitting.messages || []) {
        appendMessage(msg.role, msg.text, msg.utc, { persist: false });
    }
    syncEmptyState();
}

function loadSitting(id) {
    const sitting = switchSitting(id);
    if (!sitting) return;
    paintSitting(sitting);
    mode = "chats";
    renderChats();
}

function removeChat(id) {
    if (!window.confirm(t("confirmDeleteChat"))) return;
    const next = deleteSitting(id);
    if (next) paintSitting(next);
    else {
        const chat = document.getElementById("chatContainer");
        chat.innerHTML = "";
        resetChatTimestamps();
        syncEmptyState();
    }
    mode = "chats";
    renderChats();
}

export function newChat() {
    startNewSitting();
    const chat = document.getElementById("chatContainer");
    chat.innerHTML = "";
    resetChatTimestamps();
    syncEmptyState();
    mode = "chats";
    renderChats();
    closeMobileSidebar();
}

export function closeMobileSidebar() {
    document.getElementById("sidebar")?.classList.remove("is-open");
    document.getElementById("sidebarBackdrop")?.classList.add("hidden");
    const toggle = document.getElementById("sidebarToggle");
    if (toggle) toggle.setAttribute("aria-expanded", "false");
}

export function openMobileSidebar() {
    document.getElementById("sidebar")?.classList.add("is-open");
    document.getElementById("sidebarBackdrop")?.classList.remove("hidden");
    const toggle = document.getElementById("sidebarToggle");
    if (toggle) toggle.setAttribute("aria-expanded", "true");
}

export function initSidebar() {
    const sitting = ensureCurrentSitting();
    if (sitting.messages && sitting.messages.length) {
        paintSitting(sitting);
    }
    const sidebar = document.getElementById("sidebar");
    if (sidebar?.dataset.bound === "1") {
        refreshSidebar();
        return;
    }
    if (sidebar) sidebar.dataset.bound = "1";
    document.getElementById("notesBtn")?.addEventListener("click", async () => {
        mode = "notes";
        await refreshSidebar();
    });
    document.getElementById("remindersBtn")?.addEventListener("click", async () => {
        mode = "reminders";
        await refreshSidebar();
    });
    document.getElementById("chatsBtn")?.addEventListener("click", async () => {
        mode = "chats";
        await refreshSidebar();
    });
    document.getElementById("newChatBtn")?.addEventListener("click", () => newChat());
    document.getElementById("sidebarToggle")?.addEventListener("click", () => {
        const open = document.getElementById("sidebar")?.classList.contains("is-open");
        if (open) closeMobileSidebar();
        else openMobileSidebar();
    });
    document.getElementById("sidebarBackdrop")?.addEventListener("click", () => closeMobileSidebar());
    applyI18n(document.getElementById("sidebar"));
    window.addEventListener("jarvis:sitting-updated", () => {
        if (mode === "chats") renderChats();
    });
    window.addEventListener("jarvis:sitting-repaint", () => {
        const current = getSitting(getCurrentSittingId());
        if (current) paintSitting(current);
    });
    refreshSidebar();
}
