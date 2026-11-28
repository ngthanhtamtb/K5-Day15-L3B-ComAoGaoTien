/* Runtime configuration. The UI is served by the EduGuard backend at /ui, so the API is
 * same-origin by default. Override for a separate dev server:
 *   localStorage.setItem("eduguard.apiBase", "http://127.0.0.1:8077/api/v1/edu")
 */
function read(key, fallback) {
  try {
    return localStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
}

export const config = {
  apiBase: read("eduguard.apiBase", "/api/v1/edu"),
  jobPollMs: 700,
  jobTimeoutMs: 15 * 60 * 1000,
};
