// Recovery from "Failed to fetch dynamically imported module".
//
// A deploy replaces the hashed chunk files (Dashboard-abc123.js ...). A tab that was opened BEFORE the deploy still
// asks for the old names, gets a 404 (nginx serves a real 404 under /assets/) and the lazy route fails. Reloading
// fetches the new index.html (never cached: see deploy/nginx.conf) and everything works again.

const KEY = "nrims_chunk_reload_at";
const MIN_GAP_MS = 10_000;

/** True for the error browsers raise when a lazy-loaded chunk cannot be fetched. */
export function isChunkLoadError(err: unknown): boolean {
  const message = err instanceof Error ? err.message : typeof err === "string" ? err : "";
  return /dynamically imported module|importing a module script failed|unable to preload|loading chunk .* failed/i.test(
    message,
  );
}

/**
 * Reload the page, at most once per MIN_GAP_MS, so a server that is really down cannot cause a reload loop.
 * Returns true when a reload was started.
 */
export function reloadOnce(now: number = Date.now()): boolean {
  try {
    const last = Number(sessionStorage.getItem(KEY) ?? 0);
    if (now - last < MIN_GAP_MS) return false;
    sessionStorage.setItem(KEY, String(now));
  } catch {
    return false; // storage blocked: without the loop guard we must not reload
  }
  window.location.reload();
  return true;
}
