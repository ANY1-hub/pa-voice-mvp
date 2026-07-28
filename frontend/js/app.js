import { getToken, login, clearAuth, getStoredUser } from "./auth.js";
import { sendText, sendVoice, setStatus } from "./chat.js";
import { startRecordingSession } from "./audio.js";

// ------------------------------------------------------------------
// DOM
// ------------------------------------------------------------------
const loginScreen  = document.getElementById("loginScreen");
const appScreen    = document.getElementById("appScreen");
const loginForm    = document.getElementById("loginForm");
const loginError   = document.getElementById("loginError");
const speakBtn     = document.getElementById("speakBtn");
const speakHint    = document.getElementById("speakHint");
const recIndicator = document.getElementById("recIndicator");
const textInput    = document.getElementById("textInput");
const sendBtn      = document.getElementById("sendBtn");
const logoutBtn    = document.getElementById("logoutBtn");
const userLabel    = document.getElementById("userLabel");

let isRecording = false;
let isProcessing = false;
let currentStop = null;

// ------------------------------------------------------------------
// UI helpers
// ------------------------------------------------------------------
function showLogin() {
    loginScreen.classList.remove("hidden");
    appScreen.classList.add("hidden");
}

function showApp() {
    loginScreen.classList.add("hidden");
    appScreen.classList.remove("hidden");
    const user = getStoredUser();
    userLabel.textContent = user.email || user.username || "User";
}

function setProcessing(on) {
    isProcessing = on;
    speakBtn.disabled = on;
    sendBtn.disabled = on;
    textInput.disabled = on;
}

// ------------------------------------------------------------------
// Events
// ------------------------------------------------------------------
loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    loginError.classList.add("hidden");
    const email = document.getElementById("loginEmail").value.trim();
    const password = document.getElementById("loginPassword").value;

    try {
        await login(email, password);
        showApp();
    } catch (err) {
        loginError.textContent = err.message || "Login failed";
        loginError.classList.remove("hidden");
    }
});

logoutBtn.addEventListener("click", () => {
    clearAuth();
    document.getElementById("chatContainer").innerHTML = "";
    showLogin();
});

window.addEventListener("jarvis:unauthorized", () => {
    showLogin();
});

// Toggle recording: click to start, click again to stop → WAV → backend
speakBtn.addEventListener("click", async () => {
    if (isProcessing) return;

    // ---- Stop ----
    if (isRecording) {
        isRecording = false;
        speakBtn.classList.remove("recording");
        recIndicator.classList.add("hidden");
        speakHint.textContent = "Click to speak";

        setProcessing(true);
        setStatus("Converting & thinking…");
        try {
            const wavBlob = await currentStop(); // from startRecordingSession
            await sendVoice(wavBlob);
        } catch (err) {
            setStatus(err.message || "Voice request failed", true);
        } finally {
            currentStop = null;
            setProcessing(false);
        }
        return;
    }

    // ---- Start ----
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
    }
});

sendBtn.addEventListener("click", async () => {
    const text = textInput.value.trim();
    if (!text || isProcessing) return;
    textInput.value = "";
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
if (getToken()) {
    showApp();
} else {
    showLogin();
}
