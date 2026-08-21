import {
    API_BASE,
    TOKEN_KEY,
    USER_KEY,
    defaultApiBase,
    setApiBase,
} from "./config.js?v=2026-08-21-signin";

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

/** Public: whether the first SuperUser still needs to be created. */
export async function getBootstrapStatus() {
    const res = await fetch(`${API_BASE}/api/v1/auth/bootstrap-status`, {
        signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) throw new Error("Could not check bootstrap status");
    return res.json(); // { needs_bootstrap: bool }
}

/** Call the one configured API origin (dev :8000, or test override). */
export async function connectApi() {
    const base = defaultApiBase();
    const res = await fetch(`${base}/api/v1/auth/bootstrap-status`, {
        signal: AbortSignal.timeout(5000),
    });
    if (!res.ok) {
        throw new Error(`bootstrap-status ${res.status}`);
    }
    setApiBase(base);
    return await res.json();
}

/** Bootstrap only – first user becomes SuperUser. */
export async function register(email, password) {
    const res = await fetch(`${API_BASE}/api/v1/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Registration failed");
    }
    return res.json(); // UserPublic
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

    const user = await fetchMe(token);
    setAuth(token, user);
    return user;
}

export async function fetchMe(token) {
    const res = await fetch(`${API_BASE}/api/v1/auth/me`, {
        headers: { Authorization: `Bearer ${token || getToken()}` },
    });
    if (!res.ok) throw new Error("Could not load user profile");
    return res.json();
}

/** Authenticated password change – clears must_change_password. */
export async function changePassword(currentPassword, newPassword) {
    const res = await api("/api/v1/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            current_password: currentPassword,
            new_password: newPassword,
        }),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Password change failed");
    }
    const data = await res.json();
    if (!data.access_token) throw new Error("No token received");
    const { access_token, token_type, ...user } = data;
    setAuth(access_token, user);
    return user;
}

/** Browser IANA timezone so spoken clock times are the user's wall clock. */
export function browserTimeZone() {
    try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone || "";
    } catch {
        return "";
    }
}

/** Persist the browser IANA timezone on the user record. */
export async function setTimezone(timezone) {
    const tz = timezone || browserTimeZone();
    if (!tz) return null;
    const res = await api("/api/v1/auth/timezone", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ timezone: tz }),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Could not save timezone");
    }
    const user = await res.json();
    setAuth(getToken(), user);
    return user;
}

/** Preferred name / how Jarvis should address the user. */
export async function setDisplayName(displayName) {
    const res = await api("/api/v1/auth/display-name", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: displayName }),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Could not save name");
    }
    const user = await res.json();
    setAuth(getToken(), user);
    return user;
}

// ── Admin (SuperUser) ──────────────────────────────────────────────

export async function adminListUsers() {
    const res = await api("/api/v1/admin/users");
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to list users");
    }
    return res.json();
}

export async function adminCreateUser({ email, password, is_superuser = false, is_active = true }) {
    const res = await api("/api/v1/admin/users", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, is_superuser, is_active }),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to create user");
    }
    return res.json();
}

export async function adminUpdateUser(userId, { is_active, is_superuser }) {
    const body = {};
    if (typeof is_active === "boolean") body.is_active = is_active;
    if (typeof is_superuser === "boolean") body.is_superuser = is_superuser;

    const res = await api(`/api/v1/admin/users/${userId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    });
    if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Failed to update user");
    }
    return res.json();
}

/** Authenticated fetch helper – clears auth on 401. */
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
