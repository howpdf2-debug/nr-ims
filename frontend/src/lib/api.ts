import axios from "axios";

/**
 * Public API prefix. nginx maps `/nrims-api/` -> backend `/api/` (Vite's dev proxy does the same).
 * It is NOT `/api/`: hosting proxies such as Google Cloud Shell Web Preview intercept that generic path.
 */
export const API_BASE = "/nrims-api/v1";

/**
 * Header carrying the access token. NOT `Authorization`: a browser request with that header makes some proxies
 * (Google Cloud Shell Web Preview) answer 302 to a sign-in page, so the UI never gets its data. The backend
 * (app/deps.py) validates this header exactly like `Authorization: Bearer`.
 */
export const AUTH_HEADER = "X-NRIMS-Auth";

export const api = axios.create({
  baseURL: API_BASE,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.set(AUTH_HEADER, token);
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    // 401 = "your session is gone": only meaningful when a token was actually sent. A 401 from the login call itself
    // is just a wrong password: it must reach the login form (which shows the message), not reload the page.
    const isLogin = typeof err.config?.url === "string" && err.config.url.includes("/auth/login");
    if (err.response?.status === 401 && !isLogin && localStorage.getItem("token")) {
      localStorage.removeItem("token");
      if (window.location.pathname !== "/") window.location.assign("/");
    }
    return Promise.reject(err);
  }
);

/**
 * Human-readable message from a failed request.
 * Handles FastAPI `detail` as a string (HTTPException) or a list (422 validation errors).
 */
export function errorMessage(err: unknown, fallback = "Request failed"): string {
  if (axios.isAxiosError(err)) {
    if (!err.response) return "Cannot reach the server. Check your connection and try again.";
    const detail = err.response.data?.detail;
    if (typeof detail === "string" && detail) return detail;
    if (Array.isArray(detail)) {
      const msgs = detail.map((d: { msg?: string }) => d?.msg).filter(Boolean);
      if (msgs.length) return msgs.join("; ");
    }
  }
  return fallback;
}
