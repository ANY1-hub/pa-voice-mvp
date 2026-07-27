import { API_BASE, TOKEN_KEY, USER_KEY } from "./config.js";

export function getToken() {
    return localStorage.getItem(TOKEN_KEY);
}

export function setAuth(token, user) {
    localStorage.setItem(TOKEN_KEY, token);
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearAuth() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
}

export function getStoredUser() {
    try {
        return JSON.parse(localStorage.getItem(USER_KEY) || "{}");
    } catch {
        return {};
    }
}

export async function login(email, password) {
    const res = await fetch(`${API_BASE}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
    });

    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Login failed");
    }

    const data = await res.json();
    const token = data.access_token || data.token;
    if (!token) throw new Error("No token received");

    let user = { email };
    try {
        const meRes = await fetch(`${API_BASE}/api/v1/auth/me`, {
            headers: { Authorization: `Bearer ${token}` },
        });
        if (meRes.ok) user = await meRes.json();
    } catch (_) {}

    setAuth(token, user);
    return user;
}

export async function api(path, options = {}) {
    const token = getToken();
    const headers = { ...(options.headers || {}) };
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

    if (res.status === 401) {
        clearAuth();
        window.dispatchEvent(new Event("jarvis:unauthorized"));
        throw new Error("Session expired. Please sign in again.");
    }
    return res;
}
