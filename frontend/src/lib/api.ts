import axios from "axios";

export const api = axios.create({
  baseURL: "/api/v1", // यह Vite proxy का इस्तेमाल करेगा
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem("token");
      window.location.href = "/";
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
