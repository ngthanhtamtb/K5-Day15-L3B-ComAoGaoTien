export const mmss = (sec) => {
  const s = Math.max(0, Math.floor(Number(sec) || 0));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
};

export const fmtDate = (ts) => {
  if (!ts) return "";
  const d = new Date(ts * 1000);
  return d.toLocaleString("vi-VN", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
};

export const fmtNumber = (n) => (n === null || n === undefined ? "—" : Number(n).toLocaleString("vi-VN"));

export const fmtCost = (value, currency = "USD") =>
  value === null || value === undefined ? "chưa có giá" : `${Number(value).toLocaleString("vi-VN", { maximumFractionDigits: 6 })} ${currency}`;

export const plural = (n, word) => `${fmtNumber(n)} ${word}`;
