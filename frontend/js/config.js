function defaultApiBase() {
    if (typeof window === "undefined") {
        return "http://localhost:8000";
    }
    const host = window.location.hostname || "localhost";
    return `http://${host}:8000`;
}

export const API_BASE = defaultApiBase();
export const TOKEN_KEY = "jarvis_token";
export const USER_KEY = "jarvis_user";
