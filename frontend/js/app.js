import {
    getToken,
    setAuth,
    login,
    register,
    changePassword,
    clearAuth,
    getStoredUser,
    getBootstrapStatus,
    fetchMe,
    adminListUsers,
    adminCreateUser,
    adminUpdateUser,
} from "./auth.js";
import { sendText, sendVoice, setStatus } from "./chat.js";
import { startRecordingSession, setSpeakingHandlers, stopTts } from "./audio.js";

// ------------------------------------------------------------------
// DOM
// ------------------------------------------------------------------
const authScreen            = document.getElementById("authScreen");
const changePasswordScreen  = document.getElementById("changePasswordScreen");
const appScreen             = document.getElementById("appScreen");
const loginForm             = document.getElementById("loginForm");
const registerForm          = document.getElementById("registerForm");
const changePasswordForm    = document.getElementById("changePasswordForm");
const authError             = document.getElementById("authError");
const authSuccess           = document.getElementById("authSuccess");
const changePasswordError   = document.getElementById("changePasswordError");
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

setSpeakingHandlers({
    onStart: () => speakingIndicator?.classList.remove("hidden"),
    onEnd:   () => speakingIndicator?.classList.add("hidden"),
});

// ------------------------------------------------------------------
// Screen helpers
// ------------------------------------------------------------------
function hideAllScreens() {
    authScreen.classList.add("hidden");
    changePasswordScreen.classList.add("hidden");
    appScreen.classList.add("hidden");
    adminPanel.classList.add("hidden");
    helpPanel.classList.add("hidden");
}

function showAuth({ bootstrap = false } = {}) {
    hideAllScreens();
    authScreen.classList.remove("hidden");
    authError.classList.add("hidden");
    authSuccess.classList.add("hidden");

    if (bootstrap) {
        loginForm.classList.add("hidden");
        registerForm.classList.remove("hidden");
    } else {
        registerForm.classList.add("hidden");
        loginForm.classList.remove("hidden");
    }
}

function showChangePassword() {
    hideAllScreens();
    changePasswordScreen.classList.remove("hidden");
    changePasswordError.classList.add("hidden");
    changePasswordForm.reset();
}

function showApp() {
    hideAllScreens();
    appScreen.classList.remove("hidden");
    const user = getStoredUser();
    userLabel.textContent = user.email || "User";
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
loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    authError.classList.add("hidden");
    authSuccess.classList.add("hidden");
    const email = document.getElementById("loginEmail").value.trim();
    const password = document.getElementById("loginPassword").value;

    try {
        const user = await login(email, password);
        if (user.must_change_password) {
            showChangePassword();
        } else {
            showApp();
        }
    } catch (err) {
        showError(authError, err.message || "Login failed");
    }
});

registerForm.addEventListener("submit", async (e) => {
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

changePasswordForm.addEventListener("submit", async (e) => {
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
        await changePassword(current, next);
        showApp();
    } catch (err) {
        showError(changePasswordError, err.message || "Password change failed");
    }
});

logoutBtn.addEventListener("click", () => {
    stopTts();
    clearAuth();
    document.getElementById("chatContainer").innerHTML = "";
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
                    <span class="admin-user-email">${escapeHtml(u.email)}</span>
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
helpBtn.addEventListener("click", () => {
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
        speakHint.textContent = "Click to speak";

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
        speakHint.textContent = "Recording… click to stop";
        setStatus("Listening…");
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
    try {
        const { needs_bootstrap } = await getBootstrapStatus();
        if (needs_bootstrap) {
            showAuth({ bootstrap: true });
            return;
        }
    } catch (_) {
        // Backend unreachable – still show login
    }

    const token = getToken();
    if (!token) {
        showAuth({ bootstrap: false });
        return;
    }

    try {
        const user = await fetchMe(token);
        setAuth(token, user);

        if (user.must_change_password) {
            showChangePassword();
        } else {
            showApp();
        }
    } catch (_) {
        clearAuth();
        showAuth({ bootstrap: false });
    }
}

boot();
