import axios from "axios";

export const AUTH_HEADER = "X-NRIMS-Auth";

export const api = axios.create({
  baseURL: "/nrims-api/v1",
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
    // Login fail hone par reload nahi karna hai
    if (err.response?.status === 401 && !err.config.url?.includes("/auth/login")) {
      localStorage.removeItem("token");
      window.location.href = "/";
    }
    return Promise.reject(err);
  }
);

export function errorMessage(err: unknown, fallback = "Request failed"): string {
  if (axios.isAxiosError(err)) {
    if (!err.response) return "Cannot reach the server.";
    const detail = err.response.data?.detail;
    if (typeof detail === "string" && detail) return detail;
    if (Array.isArray(detail)) {
      const msgs = detail.map((d: { msg?: string }) => d.msg).filter(Boolean);
      if (msgs.length) return msgs.join("; ");
    }
  }
  return fallback;
}