/** Thin client for the backend's /api/v1/edu routes. */
const BASE = import.meta.env.VITE_API_BASE ?? 'http://localhost:8077';
const API = `${BASE}/api/v1/edu`;

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, init);
  if (!res.ok) throw new Error(`${res.status}: ${await res.text()}`);
  return res.json() as Promise<T>;
}
const json = (body: unknown): RequestInit => ({
  method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
});

/** Image/audio URLs from the backend are relative (/static/...) unless EDU_PUBLIC_BASE_URL is set. */
export const assetUrl = (u?: string | null) => (!u ? '' : u.startsWith('http') ? u : `${BASE}${u}`);

export const eduApi = {
  uploadDocument(file: File) {
    const fd = new FormData();
    fd.append('file', file);
    return req<{ docId: string; filename: string; stats: Record<string, number>; markdown: string }>(
      '/documents', { method: 'POST', body: fd });
  },
  getDocument: (docId: string) => req<any>(`/documents/${docId}`),
  extractQuiz: (docId: string) => req<any>(`/documents/${docId}/quiz/extract`, { method: 'POST' }),
  generateQuiz: (docId: string, opts: { numQuestions?: number; bloomMix?: Record<string, number>; engine?: string } = {}) =>
    req<any>(`/documents/${docId}/quiz/generate`, json(opts)),
  evaluateQuiz: (quizId: string, useLlm = true) => req<any>(`/quizzes/${quizId}/evaluate`, json({ useLlm })),
  updateQuestion: (quizId: string, qid: string, patch: Record<string, unknown>) =>
    req<any>(`/quizzes/${quizId}/questions/${qid}`, { ...json(patch), method: 'PATCH' }),
  applyFix: (quizId: string, qid: string, fixId: string) =>
    req<any>(`/quizzes/${quizId}/questions/${qid}/fixes/${fixId}/apply`, { method: 'POST' }),
  undoFix: (quizId: string, qid: string, fixId: string) =>
    req<any>(`/quizzes/${quizId}/questions/${qid}/fixes/${fixId}/undo`, { method: 'POST' }),
  writeScripts: (slides: unknown[], opts: { lessonTitle?: string; docId?: string; overwrite?: boolean } = {}) =>
    req<{ slides: any[] }>('/slides/scripts', json({ slides, lesson_title: opts.lessonTitle, doc_id: opts.docId, overwrite: opts.overwrite })),
  voiceSlides: (slides: unknown[], voice?: string, speed = 1) =>
    req<{ slides: any[]; manifest: { slideId: string; audioUrl: string | null; duration: number | null; script: string }[]; totalDuration: number }>(
      '/slides/voice', json({ slides, voice, speed, embed_audio_element: true })),
  synthesize: (text: string, voice?: string) => req<{ url: string; duration: number }>('/voice/synthesize', json({ text, voice })),
};
