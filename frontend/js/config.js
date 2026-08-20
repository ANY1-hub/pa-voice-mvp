export const TOKEN_KEY = "jarvis_token";
export const USER_KEY = "jarvis_user";

/**
 * Dev: Voice UI on :5500, API on :8000.
 * FastAPI can also serve the UI (Docker / pytest) — then same origin.
 */
export function defaultApiBase() {
    if (typeof window === "undefined") {
        return "http://127.0.0.1:8000";
    }
    const port = window.location.port;
    if (port === "8000" || !port) {
        return "";
    }
    const host = window.location.hostname || "127.0.0.1";
    const apiHost = host === "localhost" ? "127.0.0.1" : host;
    return `http://${apiHost}:8000`;
}

export let API_BASE = defaultApiBase();

export function setApiBase(base) {
    API_BASE = base || "";
}

/** This page first (pytest / Docker), then :8000 (python -m http.server 5500). */
export function apiBaseCandidates() {
    const bases = [""];
    if (typeof window === "undefined") {
        return bases;
    }
    const backend = defaultApiBase();
    if (backend && !bases.includes(backend)) {
        bases.push(backend);
    }
    return bases;
}
