/* Tiny observable store for cross-screen state (latest trace, toasts, plan, busy flag).
 * Screen-local state stays inside each screen module. */

export function createStore(initial) {
  let state = { ...initial };
  const subs = new Set();
  return {
    get: () => state,
    set(patch) {
      state = { ...state, ...(typeof patch === "function" ? patch(state) : patch) };
      for (const fn of subs) fn(state);
    },
    subscribe(fn) {
      subs.add(fn);
      return () => subs.delete(fn);
    },
  };
}

export const store = createStore({
  trace: null,        // { label, summary } of the last call that ran a model
  toasts: [],
  plan: null,
  llm: null,
});

let toastId = 0;
/** Short feedback (auto-dismiss 4.5s). `action` = { label, run } adds an inline button, e.g. Undo. */
export function toast(message, tone = "info", ms = 4500, action = null) {
  const id = ++toastId;
  const dismiss = () => store.set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
  store.set((s) => ({ toasts: [...s.toasts, { id, message, tone, action, dismiss }] }));
  setTimeout(dismiss, action ? Math.max(ms, 7000) : ms);
}

export function setTrace(label, summary) {
  if (summary) store.set({ trace: { label, summary, at: Date.now() } });
}

/* per-viewer conveniences only (selected template, voice…) — never required for correctness */
export const prefs = {
  get(key, fallback) {
    try {
      const v = localStorage.getItem("eduguard.pref." + key);
      return v === null ? fallback : JSON.parse(v);
    } catch {
      return fallback;
    }
  },
  set(key, value) {
    try {
      localStorage.setItem("eduguard.pref." + key, JSON.stringify(value));
    } catch {
      /* storage blocked: ignore */
    }
  },
};
