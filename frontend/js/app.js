import {
    getToken,
    setAuth,
    login,
    register,
    changePassword,
    setDisplayName,
    clearAuth,
    getStoredUser,
    connectApi,
    fetchMe,
    adminListUsers,
    adminCreateUser,
    adminUpdateUser,
    api,
} from "./auth.js";
import { sendText, sendVoice, setStatus, resetChatTimestamps, appendMessage } from "./chat.js";
import { startRecordingSession, setSpeakingHandlers, stopTts, playBase64Audio } from "./audio.js";
import { applyI18n, getLang, setLang, t } from "./i18n.js";
import { API_BASE } from "./config.js?v=2026-08-21-signin";

// ------------------------------------------------------------------
// DOM
// ------------------------------------------------------------------
const authScreen            = document.getElementById("authScreen");
const changePasswordScreen  = document.getElementById("changePasswordScreen");
const displayNameScreen     = document.getElementById("displayNameScreen");
const appScreen             = document.getElementById("appScreen");
const loginForm             = document.getElementById("loginForm");
const registerForm          = document.getElementById("registerForm");
const changePasswordForm    = document.getElementById("changePasswordForm");
const displayNameForm       = document.getElementById("displayNameForm");
const authError             = document.getElementById("authError");
const authSuccess           = document.getElementById("authSuccess");
const authStatusHint        = document.getElementById("authStatusHint");
const changePasswordError   = document.getElementById("changePasswordError");
const displayNameError      = document.getElementById("displayNameError");
const speakBtn              = document.getElementById("speakBtn");
const speakHint             = document.getElementById("speakHint");
const recIndicator          = document.getElementById("recIndicator");
const speakingIndicator     = document.getElementById("speakingIndicator");
const textInput             = document.getElementById("textInput");
const sendBtn               = document.getElementById("sendBtn");
const logoutBtn             = document.getElementById("logoutBtn");
const userLabel             = document.getElementById("userLabel");
const adminBtn              = document.getElementById("adminBtn");
const adminPanel            = document.getElementById("adminPanel");
const adminCloseBtn         = document.getElementById("adminCloseBtn");
const adminCreateForm       = document.getElementById("adminCreateForm");
const adminCreateError      = document.getElementById("adminCreateError");
const adminCreateSuccess    = document.getElementById("adminCreateSuccess");
const adminUserList         = document.getElementById("adminUserList");
const helpBtn       = document.getElementById("helpBtn");
const helpPanel     = document.getElementById("helpPanel");
const helpCloseBtn  = document.getElementById("helpCloseBtn");

let isRecording = false;
let isProcessing = false;
let isStarting = false;
let currentStop = null;
let dueTimer = null;
const DUE_POLL_MS = 15000;

setSpeakingHandlers({
    onStart: () => speakingIndicator?.classList.remove("hidden"),
    onEnd:   () => speakingIndicator?.classList.add("hidden"),
});

// ------------------------------------------------------------------
// Screen helpers
// ------------------------------------------------------------------
function hideEl(el) {
    el?.classList.add("hidden");
}

function showEl(el) {
    el?.classList.remove("hidden");
}

function on(el, event, handler) {
    el?.addEventListener(event, handler);
}

function hideAllScreens() {
    hideEl(authScreen);
    hideEl(changePasswordScreen);
    hideEl(displayNameScreen);
    hideEl(appScreen);
    hideEl(adminPanel);
    hideEl(helpPanel);
}

function stopDuePoll() {
    if (dueTimer) {
        clearInterval(dueTimer);
        dueTimer = null;
    }
}

async function tickDueReminders() {
    if (isRecording || isProcessing) return;
    try {
        const res = await api("/api/v1/reminders/due");
        if (!res.ok) return;
        const data = await res.json();
        for (const item of data.reminders || []) {
            appendMessage("jarvis", item.text);
            playBase64Audio(item.audio_base64);
            await api(`/api/v1/reminders/${item.id}/ack`, { method: "POST" });
        }
    } catch (_) {
        /* 401 is handled by api() */
    }
}

function startDuePoll() {
    stopDuePoll();
    tickDueReminders();
    dueTimer = setInterval(tickDueReminders, DUE_POLL_MS);
}

function showAuth({ bootstrap = false } = {}) {
    stopDuePoll();
    hideAllScreens();
    showEl(authScreen);
    hideEl(authError);
    hideEl(authSuccess);
    hideEl(authStatusHint);

    if (bootstrap) {
        hideEl(loginForm);
        showEl(registerForm);
    } else {
        hideEl(registerForm);
        showEl(loginForm);
    }
}

function showChangePassword() {
    stopDuePoll();
    hideAllScreens();
    showEl(changePasswordScreen);
    hideEl(changePasswordError);
    changePasswordForm?.reset();
}

function showDisplayName() {
    stopDuePoll();
    hideAllScreens();
    showEl(displayNameScreen);
    hideEl(displayNameError);
    displayNameForm?.reset();
    applyI18n();
}

function routeAfterAuth(user) {
    if (user.must_change_password) {
        showChangePassword();
    } else if (!user.display_name) {
        showDisplayName();
    } else {
        showApp();
    }
}

function showApp() {
    hideAllScreens();
    appScreen.classList.remove("hidden");
    startDuePoll();
    const user = getStoredUser();
    userLabel.textContent = user.display_name || user.email || "User";
    if (user.is_superuser) {
        adminBtn.classList.remove("hidden");
    } else {
        adminBtn.classList.add("hidden");
    }
}

function setProcessing(on) {
    isProcessing = on;
    speakBtn.disabled = on;
    sendBtn.disabled = on;
    textInput.disabled = on;
}

function showError(el, msg) {
    el.textContent = msg;
    el.classList.remove("hidden");
}

function showSuccess(el, msg) {
    el.textContent = msg;
    el.classList.remove("hidden");
}

// ------------------------------------------------------------------
// Auth events
// ------------------------------------------------------------------
on(loginForm, "submit", async (e) => {
    e.preventDefault();
    authError.classList.add("hidden");
    authSuccess.classList.add("hidden");
    const email = document.getElementById("loginEmail").value.trim();
    const password = document.getElementById("loginPassword").value;

    try {
        const user = await login(email, password);
        routeAfterAuth(user);
    } catch (err) {
        showError(authError, err.message || "Login failed");
    }
});

on(registerForm, "submit", async (e) => {
    e.preventDefault();
    authError.classList.add("hidden");
    authSuccess.classList.add("hidden");

    const email = document.getElementById("regEmail").value.trim();
    const password = document.getElementById("regPassword").value;
    const password2 = document.getElementById("regPassword2").value;

    if (password !== password2) {
        showError(authError, "Passwords do not match");
        return;
    }
    if (password.length < 12) {
        showError(authError, "Password must be at least 12 characters");
        return;
    }

    try {
        await register(email, password);
        showAuth({ bootstrap: false });
        document.getElementById("loginEmail").value = email;
        showSuccess(authSuccess, "SuperUser created. Please sign in.");
    } catch (err) {
        showError(authError, err.message || "Registration failed");
    }
});

on(changePasswordForm, "submit", async (e) => {
    e.preventDefault();
    changePasswordError.classList.add("hidden");

    const current = document.getElementById("currentPassword").value;
    const next = document.getElementById("newPassword").value;
    const next2 = document.getElementById("newPassword2").value;

    if (next !== next2) {
        showError(changePasswordError, "New passwords do not match");
        return;
    }
    if (next.length < 12) {
        showError(changePasswordError, "New password must be at least 12 characters");
        return;
    }

    try {
        const user = await changePassword(current, next);
        routeAfterAuth(user);
    } catch (err) {
        showError(changePasswordError, err.message || "Password change failed");
    }
});

on(displayNameForm, "submit", async (e) => {
    e.preventDefault();
    displayNameError.classList.add("hidden");

    const name = document.getElementById("displayNameInput").value.trim();
    if (!name) {
        showError(displayNameError, t("displayNameRequired"));
        return;
    }

    try {
        const user = await setDisplayName(name);
        routeAfterAuth(user);
    } catch (err) {
        showError(displayNameError, err.message || t("displayNameFailed"));
    }
});

logoutBtn.addEventListener("click", () => {
    stopTts();
    clearAuth();
    document.getElementById("chatContainer").innerHTML = "";
    resetChatTimestamps();
    boot();
});

window.addEventListener("jarvis:unauthorized", () => {
    stopTts();
    boot();
});

// ------------------------------------------------------------------
// Admin panel
// ------------------------------------------------------------------
adminBtn.addEventListener("click", async () => {
    adminPanel.classList.remove("hidden");
    adminCreateError.classList.add("hidden");
    adminCreateSuccess.classList.add("hidden");
    await refreshUserList();
});

adminCloseBtn.addEventListener("click", () => {
    adminPanel.classList.add("hidden");
});

adminCreateForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    adminCreateError.classList.add("hidden");
    adminCreateSuccess.classList.add("hidden");

    const email = document.getElementById("adminEmail").value.trim();
    const password = document.getElementById("adminPassword").value;
    const is_superuser = document.getElementById("adminIsSuperuser").checked;
    const is_active = document.getElementById("adminIsActive").checked;

    try {
        await adminCreateUser({ email, password, is_superuser, is_active });
        adminCreateForm.reset();
        document.getElementById("adminIsActive").checked = true;
        showSuccess(adminCreateSuccess, `User ${email} created (must change password on first login).`);
        await refreshUserList();
    } catch (err) {
        showError(adminCreateError, err.message || "Create failed");
    }
});

async function refreshUserList() {
    adminUserList.innerHTML = `<p class="text-muted">Loading…</p>`;
    try {
        const users = await adminListUsers();
        if (!users.length) {
            adminUserList.innerHTML = `<p class="text-muted">No users</p>`;
            return;
        }
        adminUserList.innerHTML = users.map((u) => `
            <div class="admin-user-row" data-id="${u.id}">
                <div class="admin-user-info">
                    <span class="admin-user-email">${escapeHtml(u.display_name ? `${u.display_name} · ${u.email}` : u.email)}</span>
                    <span class="admin-user-badges">
                        ${u.is_superuser ? '<span class="badge badge-super">Super</span>' : ""}
                        ${u.is_active ? '<span class="badge badge-active">Active</span>' : '<span class="badge badge-inactive">Inactive</span>'}
                        ${u.must_change_password ? '<span class="badge badge-force">Force change</span>' : ""}
                    </span>
                </div>
                <div class="admin-user-actions">
                    <button class="btn-ghost btn-sm" data-action="toggle-active">${u.is_active ? "Deactivate" : "Activate"}</button>
                    <button class="btn-ghost btn-sm" data-action="toggle-super">${u.is_superuser ? "Revoke Super" : "Make Super"}</button>
                </div>
            </div>
        `).join("");

        adminUserList.querySelectorAll("[data-action]").forEach((btn) => {
            btn.addEventListener("click", async () => {
                const row = btn.closest(".admin-user-row");
                const userId = row.dataset.id;
                const user = users.find((x) => x.id === userId);
                if (!user) return;

                const action = btn.dataset.action;
                const payload = {};
                if (action === "toggle-active") payload.is_active = !user.is_active;
                if (action === "toggle-super") payload.is_superuser = !user.is_superuser;

                try {
                    await adminUpdateUser(userId, payload);
                    await refreshUserList();
                } catch (err) {
                    alert(err.message || "Update failed");
                }
            });
        });
    } catch (err) {
        adminUserList.innerHTML = `<p class="error-msg">${escapeHtml(err.message)}</p>`;
    }
}

function escapeHtml(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;");
}

// ------------------------------------------------------------------
// Help Button
// ------------------------------------------------------------------
function renderHelpContent() {
    const lang = getLang();
    fetch(`${API_BASE}/api/v1/skills/phrases?lang=${encodeURIComponent(lang)}`)
        .then((res) => {
            if (!res.ok) throw new Error("phrases");
            return res.json();
        })
        .then((data) => {
            const skills = data.skills || {};
            Object.entries(skills).forEach(([skill, phrases]) => {
                const ul = document.getElementById(`help-${skill}`);
                if (!ul) return;
                ul.innerHTML = (phrases || [])
                    .map((p) => `<li>${escapeHtml(p)}</li>`)
                    .join("");
            });
        })
        .catch(() => {
            /* keep last successful list */
        });
}

function refreshI18n() {
    applyI18n();
    renderHelpContent();
    if (!isRecording) {
        speakHint.textContent = t("speakHint");
    }
}

document.querySelectorAll(".lang-flag").forEach((btn) => {
    btn.addEventListener("click", () => {
        setLang(btn.dataset.lang);
        refreshI18n();
    });
});

helpBtn.addEventListener("click", () => {
    refreshI18n();
    helpPanel.classList.remove("hidden");
});

helpCloseBtn.addEventListener("click", () => {
    helpPanel.classList.add("hidden");
});


// ------------------------------------------------------------------
// Voice / Text
// ------------------------------------------------------------------
speakBtn.addEventListener("click", async () => {
    if (isProcessing || isStarting) return;

    if (isRecording) {
        isRecording = false;
        speakBtn.classList.remove("recording");
        recIndicator.classList.add("hidden");
        speakHint.textContent = t("speakHint");

        setProcessing(true);
        setStatus("Converting & thinking…");
        try {
            const wavBlob = await currentStop();
            await sendVoice(wavBlob);
        } catch (err) {
            setStatus(err.message || "Voice request failed", true);
        } finally {
            currentStop = null;
            setProcessing(false);
        }
        return;
    }

    stopTts();
    isStarting = true;
    try {
        const session = await startRecordingSession();
        currentStop = session.stop;
        isRecording = true;
        speakBtn.classList.add("recording");
        recIndicator.classList.remove("hidden");
        speakHint.textContent = t("speakRecording");
        setStatus(t("listening"));
    } catch (err) {
        setStatus("Microphone access denied or unavailable", true);
    } finally {
        isStarting = false;
    }
});

sendBtn.addEventListener("click", async () => {
    const text = textInput.value.trim();
    if (!text || isProcessing) return;
    textInput.value = "";
    stopTts();
    setProcessing(true);
    try {
        await sendText(text);
    } catch (err) {
        setStatus(err.message || "Request failed", true);
    } finally {
        setProcessing(false);
    }
});

textInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        sendBtn.click();
    }
});

// ------------------------------------------------------------------
// Boot
// ------------------------------------------------------------------
async function boot() {
    setLang(getLang());
    refreshI18n();

    let needsBootstrap = false;
    try {
        const status = await connectApi();
        needsBootstrap = Boolean(status && status.needs_bootstrap);
    } catch (err) {
        console.error("bootstrap-status failed", err);
        hideAllScreens();
        showEl(authScreen);
        hideEl(loginForm);
        hideEl(registerForm);
        showError(authError, t("bootstrapStatusFailed"));
        return;
    }

    if (needsBootstrap) {
        showAuth({ bootstrap: true });
        return;
    }

    const token = getToken();
    if (!token) {
        showAuth({ bootstrap: false });
        return;
    }

    try {
        const user = await fetchMe(token);
        setAuth(token, user);
        routeAfterAuth(user);
    } catch (_) {
        clearAuth();
        showAuth({ bootstrap: false });
    }
}

boot();
