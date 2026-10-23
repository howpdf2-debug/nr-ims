// Role of the logged-in user, read from the (unsigned) JWT payload for UI gating ONLY.
// The server enforces every permission; this just avoids showing buttons that would answer 403.
// Roadmap Phase 4 replaces localStorage tokens, and this helper with it.

export function getRole(): string | null {
  const token = localStorage.getItem("token");
  if (!token) return null;
  try {
    const payload: unknown = JSON.parse(atob(token.split(".")[1]));
    if (payload && typeof payload === "object" && "role" in payload && typeof payload.role === "string") {
      return payload.role;
    }
  } catch {
    // malformed token: treat as unknown
  }
  return null;
}
