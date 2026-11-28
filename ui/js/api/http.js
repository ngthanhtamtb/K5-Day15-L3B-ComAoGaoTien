import { config } from "../config.js";

export class ApiError extends Error {
  constructor(status, message, body) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

function token() {
  try {
    return localStorage.getItem("eduguard.token");
  } catch {
    return null;
  }
}

/** JSON request against the EduGuard API. `form` sends multipart (file upload). */
export async function request(method, path, { body, form, query } = {}) {
  const qs = query ? "?" + new URLSearchParams(Object.entries(query).filter(([, v]) => v !== undefined && v !== null)) : "";
  const headers = { Accept: "application/json" };
  const t = token();
  if (t) headers.Authorization = `Bearer ${t}`;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  let res;
  try {
    res = await fetch(config.apiBase + path + qs, { method, headers, body: payload });
  } catch (e) {
    throw new ApiError(0, "Không kết nối được tới backend. Server đã chạy chưa?", null);
  }
  const isJson = (res.headers.get("content-type") || "").includes("json");
  const data = isJson ? await res.json().catch(() => null) : await res.text();
  if (!res.ok) {
    // backend error shapes: {message}, {detail}, {detail:[{msg}]}
    const detail = data && (data.message || data.detail);
    const msg = Array.isArray(detail) ? detail.map((d) => d.msg || d).join("; ")
      : typeof detail === "object" && detail ? JSON.stringify(detail) : detail || `HTTP ${res.status}`;
    throw new ApiError(res.status, msg, data);
  }
  return data;
}

export const apiUrl = (path, query) =>
  config.apiBase + path + (query ? "?" + new URLSearchParams(query) : "");
