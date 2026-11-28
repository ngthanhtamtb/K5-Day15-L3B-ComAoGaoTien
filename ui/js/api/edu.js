/* Every EduGuard endpoint used by the UI, in one place. Screens never build URLs themselves.
 * Calls that run a model return { data, trace }; the caller forwards trace to the Agent panel. */
import { config } from "../config.js";
import { apiUrl, request } from "./http.js";

const enc = encodeURIComponent;

/* ---------------------------------------------------------------- documents */
export const documents = {
  list: () => request("GET", "/documents").then((r) => r.data),
  upload(file) {
    const form = new FormData();
    form.append("file", file);
    return request("POST", "/documents", { form });
  },
  uploadAsync(file) {
    const form = new FormData();
    form.append("file", file);
    return request("POST", "/documents/async", { form });
  },
  get: (docId, includeBlocks = false) => request("GET", `/documents/${enc(docId)}`, { query: { include_blocks: includeBlocks } }),
  page: (docId, page) => request("GET", `/documents/${enc(docId)}/pages/${page}`),
  search: (docId, q, k = 5) => request("GET", `/documents/${enc(docId)}/search`, { query: { q, k } }),
  /** document -> proposed script (checked) + figures/tables + narrated HTML slides, as one background job */
  deck: (docId, body) => request("POST", `/documents/${enc(docId)}/deck`, { body }),
};

/* ---------------------------------------------------------------- scripts (label · fix · drop — no approval step) */
export const scripts = {
  list: () => request("GET", "/scripts").then((r) => r.data),
  create: (body) => request("POST", "/scripts", { body }),
  get: (id) => request("GET", `/scripts/${enc(id)}`).then((r) => r.data),
  decide: (id, decisions) => request("POST", `/scripts/${enc(id)}/decisions`, { body: { decisions } }),
  html: (id) => request("POST", `/scripts/${enc(id)}/html`).then((r) => r.data),
  buildSlides: (id, template) => request("POST", `/scripts/${enc(id)}/slides`, { body: { template } }).then((r) => r.data),
  voiceEstimate: (id, voice, speed) => request("POST", `/scripts/${enc(id)}/voice/estimate`, { body: { voice, speed } }).then((r) => r.data),
  startVoice: (id, voice, speed) => request("POST", `/scripts/${enc(id)}/voice`, { body: { voice, speed } }),
};

export const templates = { list: () => request("GET", "/templates").then((r) => r.data) };
export const voices = { list: () => request("GET", "/voice/voices") };

/* ---------------------------------------------------------------- quizzes */
export const quizzes = {
  list: () => request("GET", "/quizzes").then((r) => r.data),
  generate: (docId, body) => request("POST", `/documents/${enc(docId)}/quiz/generate`, { body }),
  extract: (docId) => request("POST", `/documents/${enc(docId)}/quiz/extract`),
  get: (id) => request("GET", `/quizzes/${enc(id)}`),
  evaluate: (id, useLlm = true) => request("POST", `/quizzes/${enc(id)}/evaluate`, { body: { useLlm } }),
  update: (id, qid, patch) => request("PATCH", `/quizzes/${enc(id)}/questions/${enc(qid)}`, { body: patch }),
  decide: (id, qid, action) => request("POST", `/quizzes/${enc(id)}/questions/${enc(qid)}/decision`, { body: { action } }).then((r) => r.data),
  reverify: (id, qid) => request("POST", `/quizzes/${enc(id)}/questions/${enc(qid)}/verify`),
  applyFix: (id, qid, fixId, undo = false) =>
    request("POST", `/quizzes/${enc(id)}/questions/${enc(qid)}/fixes/${enc(fixId)}/${undo ? "undo" : "apply"}`),
  pdfUrl: (id, answers) => apiUrl(`/quizzes/${enc(id)}/pdf`, { answers: answers ? "true" : "false" }),
};

/* ---------------------------------------------------------------- jobs */
export const jobs = {
  get: (id) => request("GET", `/jobs/${enc(id)}`),
  cancel: (id) => request("POST", `/jobs/${enc(id)}/cancel`),
  /** Poll until the job ends. onProgress(snapshot) on every change. Resolves with the final snapshot. */
  async wait(id, onProgress, { signal } = {}) {
    const started = Date.now();
    let last = "";
    for (;;) {
      if (signal?.aborted) throw new DOMException("aborted", "AbortError");
      const snap = await jobs.get(id);
      const key = `${snap.status}|${snap.progress_pct}|${snap.message}`;
      if (key !== last) {
        last = key;
        onProgress?.(snap);
      }
      if (["done", "failed", "cancelled"].includes(snap.status)) return snap;
      if (Date.now() - started > config.jobTimeoutMs) throw new Error("Job chạy quá lâu");
      await new Promise((r) => setTimeout(r, config.jobPollMs));
    }
  },
};

/* ---------------------------------------------------------------- account / system */
export const system = {
  plans: () => request("GET", "/plans"),
  myPlan: () => request("GET", "/me/plan"),
  llmStatus: () => request("GET", "/llm/status"),
};
