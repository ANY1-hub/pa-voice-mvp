export const TOKEN_KEY = "jarvis_token";
export const USER_KEY = "jarvis_user";

/** Human development: `python -m http.server 5500` in frontend/. Never the API. */
export const DEV_UI_PORT = "5500";
/** Human development: `uvicorn src.main:app --port 8000`. */
export const DEV_API_PORT = "8000";

/**
 * API origin for this page. No probing, no fallback list.
 *
 * Human workflow (reserved): UI :5500 → API :8000 on the same hostname.
 * Docker / `uvicorn --port 8000` serving the UI: same origin.
 * Pytest must NOT use 5500/8000. It sets ``window.JARVIS_API_BASE`` (usually
 * ``""``) before modules load so it talks to its own ephemeral server.
 *
 * @param {{ hostname?: string, port?: string } | null} [loc]
 */
export function defaultApiBase(loc) {
    if (typeof window !== "undefined" && window.JARVIS_API_BASE !== undefined) {
        return window.JARVIS_API_BASE;
    }
    if (!loc && typeof window === "undefined") {
        return `http://127.0.0.1:${DEV_API_PORT}`;
    }
    const place = loc || window.location;
    const port = String(place.port || "");
    if (port === DEV_API_PORT || port === "") {
        return "";
    }
    // Windows: localhost often resolves to ::1; uvicorn is on IPv4 127.0.0.1.
    const host = place.hostname || "127.0.0.1";
    const ipv4 =
        host === "localhost" || host === "[::1]" || host === "::1"
            ? "127.0.0.1"
            : host;
    const wrapped =
        ipv4.includes(":") && !ipv4.startsWith("[") ? `[${ipv4}]` : ipv4;
    return `http://${wrapped}:${DEV_API_PORT}`;
}

export let API_BASE = defaultApiBase();

export function setApiBase(base) {
    API_BASE = base || "";
}

/**
 * Single origin only. Do not add same-origin as a second guess — that 404s
 * on ``python -m http.server ${DEV_UI_PORT}``.
 *
 * @param {{ hostname?: string, port?: string } | null} [loc]
 */
export function apiBaseCandidates(loc) {
    return [defaultApiBase(loc)];
}
