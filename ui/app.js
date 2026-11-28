"use strict";
/* ScriptGuard — giao diện thuần JS gọi API (docs/api.md). Mọi chuỗi từ API chỉ đi vào DOM qua text node. */

const LABEL = {
  KHOP_NGUON: ["Khớp nguồn", "b-ok"], SAI_NGUON: ["Sai / mâu thuẫn nguồn", "b-bad"],
  THIEU_NGUON: ["Thiếu nguồn", "b-warn"], TU_CHOI: ["Từ chối xử lý", "b-refuse"],
};
const DECISION = {
  chua_quyet: ["Chưa quyết định", "b-mute"], chap_nhan: ["Đã chấp nhận", "b-ok"],
  tu_choi_cau: ["Đã từ chối", "b-bad"], da_sua: ["Đã sửa", "b-warn"],
};

const S = {
  kho: null, script: null, filter: "all", sel: 0,
  slide: null, quiz: null,                 // {draft, dec:{index:{action,item,note}}, sel, gate1:{}, gate2:{}}
  panel: false, busy: false, err: "", info: "", seg: {},
};
try {
  S.scriptId = sessionStorage.getItem("sg.script") || null;
  S.slideId = sessionStorage.getItem("sg.slide") || null;
  S.quizId = sessionStorage.getItem("sg.quiz") || null;
} catch (e) { /* sessionStorage không dùng được: bỏ qua */ }
const remember = (k, v) => { try { sessionStorage.setItem("sg." + k, v); } catch (e) { /* bỏ qua */ } };

/* ---------- tiện ích DOM ---------- */
function h(tag, attrs, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else if (["disabled", "checked", "selected", "controls"].includes(k)) e[k] = !!v;
    else if (k === "value") e.value = v;
    else e.setAttribute(k, v);
  }
  for (const kid of kids.flat(Infinity)) {
    if (kid == null || kid === false) continue;
    e.append(kid.nodeType ? kid : document.createTextNode(String(kid)));
  }
  return e;
}
const badge = (key) => { const [t, c] = LABEL[key] || [key, "b-mute"]; return h("span", { class: "badge " + c }, t); };
const go = (hash) => { location.hash = hash; };
const route = () => (location.hash || "#/import").slice(2);

async function api(method, path, body) {
  const res = await fetch(path, {
    method, headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch (e) { /* không phải JSON */ }
  if (!res.ok) {
    const d = data && data.detail;
    throw new Error(typeof d === "string" ? d : (d ? JSON.stringify(d) : "Lỗi " + res.status));
  }
  return data;
}
async function act(fn, okMsg) {
  if (S.busy) return;
  S.busy = true; S.err = ""; S.info = ""; render();
  try { await fn(); if (okMsg) S.info = okMsg; }
  catch (e) { S.err = e.message || String(e); }
  S.busy = false; render();
}
async function getSeg(id) {
  if (!id) return null;
  if (S.seg[id] !== undefined) return S.seg[id];
  try { S.seg[id] = await api("GET", "/api/segments/" + encodeURIComponent(id)); } catch (e) { S.seg[id] = null; }
  return S.seg[id];
}
const sum = (a, f) => a.reduce((s, x) => s + (f(x) || 0), 0);
const fmtDate = (d) => (d || "").split("-").reverse().join("/");

/* ---------- khung chung ---------- */
function stepper(steps, cur) {
  return h("ol", { class: "steps" }, steps.map((t, i) =>
    h("li", { class: i < cur ? "done" : i === cur ? "on" : "" }, h("span", { class: "n" }, i < cur ? "✓" : i + 1), t)));
}
function feedback() {
  return [S.err && h("div", { class: "note err", role: "alert" }, S.err), S.info && h("div", { class: "note okk" }, S.info)];
}
function busyBtn(text, onclick, opts = {}) {
  return h("button", { class: opts.cls || "primary", disabled: S.busy || opts.disabled, onclick },
    S.busy && opts.spin ? h("span", { class: "spin" }) : null, text);
}
function sourceBox(seg, title) {
  if (!seg) return h("div", { class: "hint" }, "Không có đoạn nguồn cho mục này.");
  return h("div", { class: "src" },
    h("div", { class: "h" }, h("strong", {}, seg.segment_id), h("span", {}, seg.session || ""), h("span", {}, "Cập nhật " + fmtDate(seg.updated_date)),
      h("span", { class: "badge b-ok" }, "Mã đoạn có thật trong kho")),
    seg.source_title ? h("div", { class: "hint" }, seg.source_title) : null,
    h("p", {}, seg.full_text), title ? null : null);
}

/* ---------- 1 · Nhập bản nháp ---------- */
let importBuoi = null, importText = "";
function viewImport() {
  if (!S.kho) { api("GET", "/api/kho").then((k) => { S.kho = k; importBuoi = importBuoi || (k[0] && k[0].buoi); render(); }).catch((e) => { S.err = e.message; render(); }); return h("p", {}, "Đang tải kho tài liệu…"); }
  const picked = importBuoi || (S.kho[0] && S.kho[0].buoi);
  return h("div", {},
    h("h1", {}, "Đưa bản nháp kịch bản vào rà soát"),
    h("p", { class: "lead" }, "ScriptGuard đối chiếu từng câu khẳng định với kho tài liệu gốc rồi gắn nhãn gợi ý kèm lý do và mã đoạn. Bạn là người chấp nhận hay từ chối từng nhãn."),
    stepper(["Nhập bản nháp", "Đối chiếu với nguồn", "Giảng viên rà soát"], 0),
    feedback(),
    h("div", { class: "grid2" },
      h("div", { class: "card" },
        h("label", { class: "f", for: "buoi" }, "Bài pre-class"),
        h("select", { id: "buoi", onchange: (e) => { importBuoi = parseInt(e.target.value, 10); } },
          S.kho.map((k) => h("option", { value: k.buoi, selected: k.buoi === picked }, k.ten))),
        h("label", { class: "f", for: "kb" }, "Bản nháp kịch bản do AI sinh"),
        h("textarea", { id: "kb", placeholder: "Dán kịch bản, mỗi câu khẳng định một dòng hoặc nối tiếp nhau…", oninput: (e) => { importText = e.target.value; } }, importText),
        h("div", { class: "hint" }, "Chỉ dán nội dung tự dựng hoặc đã ẩn danh, không kèm thông tin cá nhân học viên. Dữ liệu gửi qua API có thể được nhà cung cấp mô hình lưu lại."),
        h("div", { class: "row", style: "margin-top:12px" },
          busyBtn("Bắt đầu đối chiếu", () => { importText = document.getElementById("kb").value; return act(async () => {
            const noi_dung = importText.trim();
            if (!noi_dung) throw new Error("Hãy dán kịch bản trước.");
            const r = await api("POST", "/api/scripts", { buoi: picked, noi_dung });
            if (!r.created) throw new Error(r.message || "Hệ thống từ chối: " + r.status);
            S.script = r.script; S.scriptId = r.script.script_id; remember("script", S.scriptId); S.sel = 0; S.filter = "all";
            go("#/script");
          }); }, { spin: true }),
          h("span", { class: "hint" }, "Có thể mất vài chục giây tuỳ độ dài."))),
      h("aside", { class: "card" },
        h("h2", {}, "Kho tài liệu gốc sẽ dùng"),
        S.kho.map((k) => h("div", { style: "margin-bottom:8px" },
          h("strong", {}, k.ten), h("div", { class: "hint" }, k.so_doan + " đoạn · cập nhật " + fmtDate(k.cap_nhat) + (k.co_ban_cu ? " · có đoạn bản cũ" : "")))),
        h("h2", { style: "margin-top:16px" }, "ScriptGuard làm được gì"),
        h("p", {}, "Gắn nhãn Khớp nguồn, Sai / mâu thuẫn nguồn, Thiếu nguồn kèm lý do và mã đoạn. Không chắc thì gắn Thiếu nguồn, không đoán."),
        h("p", {}, "Không sửa kịch bản, không tự xuất bản, không làm theo chỉ dẫn nằm trong kịch bản."))));
}

/* ---------- 2 · Rà soát kịch bản ---------- */
async function ensureScript() {
  if (S.script || !S.scriptId) return;
  try { S.script = await api("GET", "/api/scripts/" + S.scriptId); } catch (e) { S.scriptId = null; }
  render();
}
function decideScript(index, action, noi_dung) {
  return act(async () => {
    S.script = await api("POST", "/api/scripts/" + S.script.script_id + "/decisions", { decisions: [{ index, action, noi_dung }] });
  });
}
function viewScript() {
  if (!S.script) { if (S.scriptId) { ensureScript(); return h("p", {}, "Đang tải kịch bản…"); } go("#/import"); return h("p"); }
  const sc = S.script, claims = sc.claims;
  const count = (k) => claims.filter((c) => c.nhan === k).length;
  const visible = claims.filter((c) => S.filter === "all" || c.nhan === S.filter);
  if (S.sel >= claims.length) S.sel = 0;
  const cur = claims[S.sel];
  const pending = claims.filter((c) => c.quyet_dinh === "chua_quyet").length;
  const matchPending = claims.filter((c) => c.nhan === "KHOP_NGUON" && c.quyet_dinh === "chua_quyet").length;
  const submitted = sc.stage !== "ra_soat";
  const chips = [["all", "Tất cả", claims.length], ["KHOP_NGUON", "Khớp nguồn", count("KHOP_NGUON")], ["SAI_NGUON", "Sai nguồn", count("SAI_NGUON")],
    ["THIEU_NGUON", "Thiếu nguồn", count("THIEU_NGUON")], ["TU_CHOI", "Từ chối", count("TU_CHOI")]];
  return h("div", {},
    h("h1", {}, "Rà soát kịch bản: Buổi " + sc.buoi),
    h("p", { class: "lead" }, sc.tong_cau + " câu khẳng định · mỗi nhãn là gợi ý của AI, giảng viên quyết định"),
    stepper(["Nhập bản nháp", "Đối chiếu với nguồn", "Giảng viên rà soát"], submitted ? 3 : 2),
    feedback(),
    sc.chen_chi_dan ? h("div", { class: "note info" }, "Trong kịch bản có câu chứa chỉ dẫn chèn cho hệ thống. Hệ thống đã tách câu đó, gắn “Từ chối xử lý” và không làm theo.") : null,
    h("div", { class: "row" }, h("strong", {}, "Đã quyết định " + sc.da_quyet + "/" + sc.tong_cau), h("span", { class: "hint" }, "Còn " + pending + " câu chưa quyết định")),
    h("div", { class: "progress", role: "progressbar", "aria-valuenow": sc.da_quyet, "aria-valuemax": sc.tong_cau }, h("i", { style: "width:" + (100 * sc.da_quyet / Math.max(1, sc.tong_cau)) + "%" })),
    h("div", { class: "chips", role: "group", "aria-label": "Lọc theo nhãn" }, chips.map(([k, t, n]) =>
      h("button", { class: "chip" + (S.filter === k ? " on" : ""), onclick: () => { S.filter = k; render(); } }, t + " " + n)),
      busyBtn("Chấp nhận mọi câu “Khớp nguồn” chưa quyết (" + matchPending + ")", () => act(async () => {
        S.script = await api("POST", "/api/scripts/" + sc.script_id + "/accept-matching");
      }), { cls: "good", disabled: !matchPending || submitted })),
    h("div", { class: "grid-review" },
      h("div", { class: "list", role: "list", "aria-label": "Danh sách câu khẳng định" }, visible.map((c) => {
        const [dt, dc] = DECISION[c.quyet_dinh];
        return h("button", { class: "item" + (c === cur ? " sel" : ""), onclick: () => { S.sel = c.index - 1; render(); } },
          h("span", { class: "no" }, String(c.index).padStart(2, "0")),
          h("span", { class: "tx" }, c.noi_dung, h("span", { class: "meta" }, badge(c.nhan), h("span", { class: "badge " + dc }, dt))));
      })),
      scriptDetail(cur, submitted)),
    h("div", { class: "navbar" },
      h("span", {}, pending ? "Còn " + pending + " câu chưa quyết định." : "Đã quyết định xong mọi câu."),
      submitted
        ? h("div", { class: "row" }, h("span", { class: "badge b-ok" }, "Đã gửi chờ duyệt"), h("button", { class: "primary", onclick: () => go("#/slide-create") }, "Tạo slide từ kịch bản này"))
        : busyBtn("Gửi chờ duyệt", () => act(async () => { S.script = await api("POST", "/api/scripts/" + sc.script_id + "/submit"); }, "Đã gửi chờ duyệt. Có thể tạo slide từ kịch bản."), { disabled: pending > 0 })));
}
let editingClaim = null;
function scriptDetail(c, submitted) {
  const lock = submitted || S.busy;
  const isRefuse = c.nhan === "TU_CHOI";
  return h("section", { class: "card", "aria-label": "Chi tiết câu đang xem" },
    h("div", { class: "row" }, h("strong", {}, "Câu " + String(c.index).padStart(2, "0") + " / " + S.script.tong_cau), badge(c.nhan),
      h("span", { class: "hint" }, "Gợi ý của AI — giảng viên quyết định")),
    h("h3", {}, "Câu trong kịch bản"), h("blockquote", {}, c.noi_dung),
    c.ly_do ? [h("h3", {}, "Vì sao gắn nhãn này"), h("p", {}, c.ly_do)] : null,
    c.de_xuat_sua ? [h("h3", {}, "Đề xuất sửa"), h("p", {}, c.de_xuat_sua)] : null,
    c.canh_bao_ma ? h("div", { class: "note" }, "Cảnh báo mã nguồn: " + c.canh_bao_ma) : null,
    c.nguon_cu ? h("div", { class: "note" }, "Đoạn cũ mâu thuẫn: " + c.nguon_cu + " (đã lỗi thời, ưu tiên đoạn mới hơn).") : null,
    c.nguon ? [h("h3", {}, "Đoạn nguồn trích dẫn"), sourceBox(c.nguon)] : (isRefuse ? null : h("p", { class: "hint" }, "Không tìm được đoạn nguồn cho câu này.")),
    editingClaim === c.index
      ? h("div", {}, h("label", { class: "f", for: "ec" }, "Sửa câu (hệ thống sẽ kiểm lại)"),
        h("textarea", { id: "ec", class: "short" }, c.de_xuat_sua || c.noi_dung),
        h("div", { class: "row", style: "margin-top:8px" },
          busyBtn("Lưu câu sửa", () => { const v = document.getElementById("ec").value; editingClaim = null; return decideScript(c.index, "edit", v); }, { disabled: lock }),
          h("button", { onclick: () => { editingClaim = null; render(); } }, "Huỷ")))
      : h("div", { class: "row", style: "margin-top:14px" },
        h("button", { class: "good", disabled: lock || isRefuse, onclick: () => decideScript(c.index, "accept") }, "Chấp nhận"),
        h("button", { class: "danger", disabled: lock, onclick: () => decideScript(c.index, "reject") }, "Từ chối"),
        h("button", { disabled: lock || isRefuse, onclick: () => { editingClaim = c.index; render(); } }, "Sửa"),
        c.quyet_dinh !== "chua_quyet" ? h("button", { disabled: lock, onclick: () => decideScript(c.index, "reset") }, "Hoàn tác") : null),
    isRefuse ? h("div", { class: "hint" }, "Câu chứa chỉ dẫn chèn nên không thể chấp nhận và sẽ không vào slide.") : null,
    h("div", { class: "row", style: "margin-top:12px" },
      h("button", { disabled: S.sel === 0, onclick: () => { S.sel--; render(); } }, "Câu trước"),
      h("button", { disabled: S.sel >= S.script.claims.length - 1, onclick: () => { S.sel++; render(); } }, "Câu tiếp theo")));
}

/* ---------- 3 · Tạo slide ---------- */
let createOpts = { so: 6, ty_le: "16:9", mau: "AI20K chuẩn", ghi_chu: true, quiz: true };
function viewSlideCreate() {
  if (!S.script) { if (S.scriptId) { ensureScript(); return h("p", {}, "Đang tải…"); } return h("div", { class: "note" }, "Chưa có kịch bản đã rà soát. ", h("a", { href: "#/import" }, "Nhập kịch bản")); }
  const sc = S.script, kept = sc.claims.filter((c) => ["chap_nhan", "da_sua"].includes(c.quyet_dinh) && c.nhan !== "TU_CHOI").length;
  const weak = sc.claims.filter((c) => ["chap_nhan", "da_sua"].includes(c.quyet_dinh) && ["SAI_NGUON", "THIEU_NGUON"].includes(c.nhan)).length;
  const pending = sc.claims.filter((c) => c.quyet_dinh === "chua_quyet").length;
  return h("div", {},
    h("h1", {}, "Tạo slide từ kịch bản"),
    h("p", { class: "lead" }, "AI dựng slide từ kịch bản đã rà soát. Mỗi ý trên slide giữ liên kết tới đoạn nguồn để bước sau bạn kiểm từng slide một."),
    stepper(["Tạo slide", "Kiểm từng slide", "Gửi chờ duyệt"], 0), feedback(),
    h("div", { class: "grid2" },
      h("div", { class: "card" },
        h("h2", {}, "Đầu vào"),
        h("p", {}, "Kịch bản Buổi " + sc.buoi + " · " + sc.tong_cau + " câu · giữ lại " + kept + " câu · " + (sc.stage === "ra_soat" ? "chưa gửi chờ duyệt" : "đã gửi chờ duyệt")),
        pending ? h("div", { class: "note err" }, "Còn " + pending + " câu chưa quyết định ở bước rà soát kịch bản. ", h("a", { href: "#/script" }, "Quay lại rà soát")) : null,
        weak ? h("div", { class: "note" }, weak + " câu bạn giữ lại có nhãn Sai / Thiếu nguồn. Slide vẫn được tạo, nhưng các ý dựa trên câu đó sẽ được kiểm lại ở bước sau.") : null,
        h("label", { class: "f", for: "so" }, "Số slide"),
        h("select", { id: "so", onchange: (e) => { createOpts.so = parseInt(e.target.value, 10); } },
          [3, 4, 6, 8, 10].map((n) => h("option", { value: n, selected: n === createOpts.so }, n + " slide"))),
        h("label", { class: "f", for: "tl" }, "Tỉ lệ khung"),
        h("select", { id: "tl", onchange: (e) => { createOpts.ty_le = e.target.value; } }, ["16:9", "4:3"].map((t) => h("option", { selected: t === createOpts.ty_le }, t))),
        h("label", { class: "f", for: "mau" }, "Mẫu trình bày"),
        h("select", { id: "mau", onchange: (e) => { createOpts.mau = e.target.value; } }, ["AI20K chuẩn", "Tối giản"].map((t) => h("option", { selected: t === createOpts.mau }, t))),
        h("label", { class: "f" }, h("input", { type: "checkbox", checked: createOpts.ghi_chu, onchange: (e) => { createOpts.ghi_chu = e.target.checked; } }), " Ghi chú người nói cho từng slide"),
        h("label", { class: "f" }, h("input", { type: "checkbox", checked: createOpts.quiz, onchange: (e) => { createOpts.quiz = e.target.checked; } }), " Kèm bộ quiz 5 câu cho cuối bài (kiểm ở mục Quiz)"),
        h("div", { class: "hint" }, "Mẫu trình bày, tỉ lệ khung và ghi chú người nói hiện chỉ được lưu lại, chưa áp dụng khi dựng slide."),
        h("div", { class: "row", style: "margin-top:12px" },
          busyBtn("Tạo slide", () => act(async () => {
            const base = { buoi: sc.buoi, script_id: sc.script_id, options: createOpts };
            const r = await api("POST", "/api/drafts", Object.assign({ kind: "slide", so_luong: createOpts.so }, base));
            if (!r.created) throw new Error(r.message || "Không tạo được slide: " + r.status);
            S.slide = freshReview(r.draft); S.slideId = r.draft.draft_id; remember("slide", S.slideId);
            if (createOpts.quiz) {
              const q = await api("POST", "/api/drafts", Object.assign({ kind: "quiz", so_luong: 5 }, base));
              if (q.created) { S.quiz = freshReview(q.draft); S.quizId = q.draft.draft_id; remember("quiz", S.quizId); }
              else S.info = "Slide đã tạo; quiz chưa tạo được: " + (q.message || q.status);
            }
            go("#/slide");
          }), { disabled: pending > 0 || !kept, spin: true }),
          h("span", { class: "hint" }, "Slide tạo ra ở trạng thái bản nháp, chưa xuất bản."))),
      h("aside", { class: "card" }, h("h2", {}, "Sau khi tạo, bạn kiểm thế nào"),
        h("ol", {}, h("li", {}, "Đi lần lượt từng slide, mỗi màn hình một slide."),
          h("li", {}, "Mỗi mục có nhãn Khớp / Sai / Thiếu nguồn và đoạn tham chiếu."),
          h("li", {}, "Bấm “Đạt” để sang mục tiếp, hoặc “Cần sửa” kèm ghi chú.")))));
}

/* ---------- 4 / 5 · Kiểm từng slide, từng câu quiz ---------- */
const freshReview = (draft) => ({ draft, dec: {}, sel: 0, gate1: {}, gate2: {}, editing: null });
async function ensureDraft(kind) {
  const id = kind === "slide" ? S.slideId : S.quizId;
  if (S[kind] || !id) return;
  try { S[kind] = freshReview(await api("GET", "/api/drafts/" + id)); } catch (e) { if (kind === "slide") S.slideId = null; else S.quizId = null; }
  render();
}
function itemLabel(st, i) { // nhãn tự kiểm theo từng mục khi số nhãn bằng số mục; nếu không thì không gán nhầm
  const n = st.draft.nhan || [];
  return n.length === st.draft.items.length ? n[i] : null;
}
function itemTitle(kind, it, i) { return kind === "slide" ? it.tieu_de : "Câu " + (i + 1); }
function fieldsFor(kind) {
  return kind === "slide"
    ? [["tieu_de", "Tiêu đề", "text"], ["y_chinh", "Ý chính (mỗi ý một dòng)", "lines"], ["loi_thuyet_trinh", "Lời thuyết trình", "area"]]
    : [["de", "Đề", "area"], ["A", "A", "text"], ["B", "B", "text"], ["C", "C", "text"], ["D", "D", "text"], ["dap_an", "Đáp án (A–D)", "text"], ["giai_thich", "Giải thích", "area"]];
}
function readItemForm(kind) {
  const out = {};
  for (const [k, , t] of fieldsFor(kind)) {
    const v = document.getElementById("f-" + k).value;
    out[k] = t === "lines" ? v.split("\n").map((x) => x.trim()).filter(Boolean) : v.trim();
  }
  return out;
}
function itemForm(kind, it) {
  return h("div", {}, fieldsFor(kind).map(([k, label, t]) => [
    h("label", { class: "f", for: "f-" + k }, label),
    t === "text" ? h("input", { type: "text", id: "f-" + k, value: it[k] || "" })
      : h("textarea", { id: "f-" + k, class: "short" }, t === "lines" ? (it[k] || []).join("\n") : (it[k] || ""))]));
}
function itemPreview(kind, it) {
  if (kind === "slide") {
    return h("div", { class: "slide-prev" }, h("h2", {}, it.tieu_de), h("ol", {}, (it.y_chinh || []).map((y) => h("li", {}, y))),
      h("h3", {}, "Lời thuyết trình"), h("p", {}, it.loi_thuyet_trinh));
  }
  const ans = String(it.dap_an || "").toUpperCase();
  return h("div", { class: "card" }, h("h2", {}, it.de),
    h("ul", { class: "opts" }, ["A", "B", "C", "D"].map((k) => h("li", { class: k === ans ? "ans" : "" }, h("span", { class: "k" }, k), h("span", {}, it[k]), k === ans ? h("span", { class: "badge b-mute" }, "AI chọn làm đáp án") : null))),
    h("h3", {}, "Giải thích đi kèm (AI sinh)"), h("p", {}, it.giai_thich));
}
function viewReview(kind) {
  const st = S[kind], idKey = kind === "slide" ? S.slideId : S.quizId, name = kind === "slide" ? "slide" : "câu quiz";
  if (!st) {
    if (idKey) { ensureDraft(kind); return h("p", {}, "Đang tải bản nháp…"); }
    return kind === "slide" ? h("div", { class: "note" }, "Chưa có bản nháp slide. ", h("a", { href: "#/slide-create" }, "Tạo slide từ kịch bản")) : quizStart();
  }
  const d = st.draft;
  if (d.stage === "cho_duyet") return reviewDone(kind, st);
  if (d.stage === "cong_2") return reviewGate2(kind, st);
  return reviewGate1(kind, st, name);
}
let quizForm = { buoi: null, chu: "", n: 5 };
function quizStart() {
  if (!S.kho) { api("GET", "/api/kho").then((k) => { S.kho = k; render(); }); return h("p", {}, "Đang tải…"); }
  quizForm.buoi = quizForm.buoi || S.kho[0].buoi;
  return h("div", {}, h("h1", {}, "Kiểm từng câu quiz"),
    h("p", { class: "lead" }, "Chưa có bộ quiz. Tạo từ chủ đề hoặc từ kịch bản đã rà soát (mục Slide, chọn kèm bộ quiz)."), feedback(),
    h("div", { class: "card", style: "max-width:520px" },
      h("label", { class: "f", for: "qb" }, "Buổi"),
      h("select", { id: "qb", onchange: (e) => { quizForm.buoi = parseInt(e.target.value, 10); } }, S.kho.map((k) => h("option", { value: k.buoi, selected: k.buoi === quizForm.buoi }, k.ten))),
      h("label", { class: "f", for: "qc" }, "Chủ đề"), h("input", { type: "text", id: "qc", value: quizForm.chu, oninput: (e) => { quizForm.chu = e.target.value; } }),
      h("label", { class: "f", for: "qn" }, "Số câu"), h("input", { type: "number", id: "qn", min: 1, max: 10, value: quizForm.n, oninput: (e) => { quizForm.n = parseInt(e.target.value, 10) || 5; } }),
      h("div", { class: "row", style: "margin-top:12px" }, busyBtn("Tạo quiz", () => act(async () => {
        if (!quizForm.chu.trim()) throw new Error("Hãy nhập chủ đề.");
        const r = await api("POST", "/api/drafts", { kind: "quiz", buoi: quizForm.buoi, chu_de: quizForm.chu, so_luong: quizForm.n });
        if (!r.created) throw new Error(r.message || "Không tạo được quiz: " + r.status);
        S.quiz = freshReview(r.draft); S.quizId = r.draft.draft_id; remember("quiz", S.quizId);
      }), { spin: true }))));
}
function reviewGate1(kind, st, name) {
  const d = st.draft, items = d.items;
  if (st.sel >= items.length) st.sel = 0;
  const i = st.sel, it = items[i], lab = itemLabel(st, i), dec = st.dec[i + 1];
  const decided = items.filter((_, k) => st.dec[k + 1]).length;
  const cls = (k) => { const x = st.dec[k + 1]; return (k === i ? "sel " : "") + (x ? (x.action === "accept" ? "d-ok" : x.action === "edit" ? "d-edit" : "d-rej") : ""); };
  getSeg(it.segment_id).then(() => { if (!S._segShown || S._segShown !== it.segment_id) { S._segShown = it.segment_id; render(); } });
  const setDec = (action, extra) => { st.dec[i + 1] = Object.assign({ action }, extra || {}); st.editing = null; if (i < items.length - 1 && action !== "edit") st.sel++; render(); };
  return h("div", {},
    h("h1", {}, kind === "slide" ? "Kiểm từng slide" : "Kiểm từng câu quiz"),
    h("p", { class: "lead" }, kind === "slide" ? "Mỗi ý trên slide được đối chiếu với tài liệu gốc." : "Mỗi câu được đối chiếu đáp án và phương án nhiễu với tài liệu gốc."),
    stepper(["Tạo", "Kiểm từng " + name, "Gửi chờ duyệt"], 1), feedback(),
    h("div", { class: "row" }, h("strong", {}, "Đã kiểm " + decided + "/" + items.length)),
    h("nav", { class: "pick", "aria-label": "Chọn mục" }, items.map((x, k) => h("button", { class: cls(k), onclick: () => { st.sel = k; st.editing = null; render(); } }, kind === "slide" ? (k + 1) + ". " + x.tieu_de : "Câu " + (k + 1)))),
    h("div", { class: "grid-review" },
      h("div", {}, itemPreview(kind, it),
        h("h3", {}, "Tài liệu tham chiếu"), sourceBox(S.seg[it.segment_id])),
      h("div", { class: "card" },
        h("div", { class: "row" }, h("strong", {}, itemTitle(kind, it, i) + " · " + (i + 1) + "/" + items.length), lab ? badge(lab.nhan) : h("span", { class: "badge b-mute" }, "Chưa có nhãn riêng"),
          h("span", { class: "hint" }, "Gợi ý của AI — giảng viên quyết định")),
        lab ? [h("p", {}, lab.ly_do || ""), lab.de_xuat_sua ? h("div", { class: "note info" }, "Đề xuất sửa: " + lab.de_xuat_sua) : null]
          : h("p", { class: "hint" }, "Nhãn tự kiểm của bản nháp không khớp từng mục. Mục được kiểm lại sau khi bạn sửa ở bước này."),
        st.gate1[i + 1] ? checkBox(st.gate1[i + 1]) : null,
        st.editing === i
          ? h("div", {}, itemForm(kind, it), h("label", { class: "f", for: "note" }, "Ghi chú (tuỳ chọn)"), h("textarea", { id: "note", class: "short" }, (dec && dec.note) || ""),
            h("div", { class: "row", style: "margin-top:8px" },
              h("button", { class: "primary", onclick: () => setDec("edit", { item: readItemForm(kind), note: document.getElementById("note").value }) }, "Lưu sửa"),
              h("button", { onclick: () => { st.editing = null; render(); } }, "Huỷ")))
          : h("div", { class: "row", style: "margin-top:12px" },
            h("button", { class: "good", disabled: S.busy, onclick: () => setDec("accept") }, i < items.length - 1 ? "Đạt — sang mục tiếp" : "Đạt"),
            h("button", { disabled: S.busy, onclick: () => { st.editing = i; render(); } }, "Cần sửa"),
            h("button", { class: "danger", disabled: S.busy, onclick: () => setDec("reject") }, "Bỏ mục này")),
        dec ? h("p", { class: "hint" }, "Quyết định hiện tại: " + ({ accept: "Đạt", edit: "Cần sửa (đã sửa)", reject: "Bỏ mục" }[dec.action]) + (dec.note ? " · ghi chú: " + dec.note : "")) : null,
        h("div", { class: "row", style: "margin-top:10px" },
          h("button", { disabled: i === 0, onclick: () => { st.sel--; st.editing = null; render(); } }, "Mục trước"),
          h("button", { disabled: i >= items.length - 1, onclick: () => { st.sel++; st.editing = null; render(); } }, "Mục tiếp theo")))),
    h("div", { class: "navbar" }, h("span", {}, decided < items.length ? "Còn " + (items.length - decided) + " mục chưa quyết định." : "Đã quyết định xong mọi mục."),
      busyBtn("Chốt cổng 1 và dựng bản", () => act(async () => {
        const decisions = items.map((_, k) => Object.assign({ index: k + 1 }, st.dec[k + 1]));
        const g = await api("POST", "/api/drafts/" + d.draft_id + "/gate1", { decisions });
        st.gate1 = g.kiem_lai_muc_sua || {};
        const kept = g.draft.items.length;
        if (!kept) throw new Error("Đã bỏ hết mục, không còn gì để dựng.");
        st.draft = await api("POST", "/api/drafts/" + d.draft_id + "/build"); st.dec = {}; st.sel = 0;
        if (kind === "slide" && Object.keys(st.draft.audio_errors || {}).length) S.info = "Có slide chưa tạo được giọng đọc (lỗi mạng): " + Object.keys(st.draft.audio_errors).join(", ");
      }), { disabled: decided < items.length, spin: true })));
}
function checkBox(c) {
  return h("div", { class: "note info" }, h("strong", {}, "Kiểm lại sau khi sửa: "), (c.nhan || []).map((x) => h("div", {}, badge(x.nhan), " ", x.ly_do || "", x.de_xuat_sua ? " · Đề xuất: " + x.de_xuat_sua : "")),
    c.chen_chi_dan ? h("div", {}, "Phát hiện chỉ dẫn chèn trong nội dung sửa.") : null);
}
function reviewGate2(kind, st) {
  const d = st.draft, f = d.files || {};
  const i = st.sel >= d.items.length ? 0 : st.sel, it = d.items[i];
  const link = (name, text) => h("a", { href: "/api/drafts/" + d.draft_id + "/files/" + name, target: "_blank", rel: "noopener" }, text);
  return h("div", {},
    h("h1", {}, kind === "slide" ? "Kiểm bản đã dựng (cổng 2)" : "Kiểm bản PDF đã dựng (cổng 2)"),
    h("p", { class: "lead" }, "Xem bản đã dựng, sửa trực tiếp nếu cần: nội dung sửa được kiểm lại, nếu sai nguồn thì có đề xuất sửa kèm nguồn."),
    stepper(["Tạo", "Kiểm từng mục", "Gửi chờ duyệt"], 2), feedback(),
    h("div", { class: "grid-review" },
      h("div", { class: "card" }, h("h2", {}, "Bản đã dựng"),
        kind === "slide"
          ? [f.slides_html ? h("iframe", { class: "deck", src: "/api/drafts/" + d.draft_id + "/files/slides_html", title: "Slide đã dựng" }) : null,
            f.slides_html ? h("p", {}, link("slides_html", "Mở slide HTML ở tab mới")) : null,
            d.items.map((x, k) => f["audio_" + (k + 1)] ? h("div", {}, h("div", { class: "hint" }, "Giọng đọc · Slide " + (k + 1) + ": " + x.tieu_de), h("audio", { controls: true, preload: "none", src: "/api/drafts/" + d.draft_id + "/files/audio_" + (k + 1) })) : h("div", { class: "hint" }, "Slide " + (k + 1) + ": chưa có giọng đọc"))]
          : [f.exam_pdf ? h("p", {}, link("exam_pdf", "Tải PDF đề")) : null, f.answer_pdf ? h("p", {}, link("answer_pdf", "Tải PDF đáp án")) : null,
            d.items.map((x, k) => h("div", { class: "hint" }, "Câu " + (k + 1) + ": " + x.de)),]),
      h("div", { class: "card" }, h("h2", {}, "Sửa trực tiếp"),
        h("div", { class: "pick" }, d.items.map((x, k) => h("button", { class: k === i ? "sel" : "", onclick: () => { st.sel = k; render(); } }, kind === "slide" ? (k + 1) + ". " + x.tieu_de : "Câu " + (k + 1)))),
        itemForm(kind, it),
        h("div", { class: "row", style: "margin-top:10px" }, busyBtn("Lưu sửa và kiểm lại", () => {
          const item = readItemForm(kind);       // đọc form TRƯỚC khi act() vẽ lại trang
          return act(async () => {
            const r = await api("POST", "/api/drafts/" + d.draft_id + "/gate2", { decisions: [{ index: i + 1, action: "edit", item }] });
            st.draft = r.draft; st.gate2 = Object.assign({}, st.gate2, r.kiem_lai_muc_sua);
          });
        }, { spin: true })),
        st.gate2[i + 1] ? checkBox(st.gate2[i + 1]) : null)),
    h("div", { class: "navbar" }, h("span", {}, "Slide / PDF ở trạng thái bản nháp, chưa xuất bản."),
      busyBtn("Gửi chờ duyệt", () => act(async () => { st.draft = await api("POST", "/api/drafts/" + d.draft_id + "/submit"); }), { spin: true })));
}
function reviewDone(kind, st) {
  const d = st.draft;
  return h("div", {}, h("h1", {}, "Đã gửi chờ duyệt"), stepper(["Tạo", "Kiểm từng mục", "Gửi chờ duyệt"], 3),
    h("div", { class: "note okk" }, "Bản " + (kind === "slide" ? "slide" : "quiz") + " ở trạng thái “chờ duyệt” (mã " + (d.review_id || d.draft_id) + "). Hệ thống không tự xuất bản và không gửi cho học viên; giảng viên tự xuất bản ngoài hệ thống."),
    h("div", { class: "row" }, h("button", { onclick: () => { S[kind] = null; if (kind === "slide") S.slideId = null; else S.quizId = null; go(kind === "slide" ? "#/slide-create" : "#/quiz"); } }, "Làm bản mới")));
}

/* ---------- Agent verify (icon + panel) ---------- */
function agentContext() {
  const r = route();
  if (r === "script" && S.script) {
    const c = S.script.claims[S.sel];
    return { title: "Rà soát kịch bản · câu " + (S.sel + 1) + "/" + S.script.tong_cau, items: c ? [{ nhan: c.nhan, text: c.noi_dung, ly_do: c.ly_do, fix: c.de_xuat_sua, seg: c.nguon }] : [],
      counts: S.script.claims, traces: S.script.traces || [], script: S.script };
  }
  const kind = r === "slide" ? "slide" : r === "quiz" ? "quiz" : null, st = kind && S[kind];
  if (st) {
    const i = Math.min(st.sel, st.draft.items.length - 1), it = st.draft.items[i], lab = it && itemLabel(st, i);
    const chk = st.gate1[i + 1] || st.gate2[i + 1];
    const items = chk ? chk.nhan.map((x) => ({ nhan: x.nhan, text: x.noi_dung, ly_do: x.ly_do, fix: x.de_xuat_sua, seg: x.segment_id && S.seg[x.segment_id] }))
      : lab && it ? [{ nhan: lab.nhan, text: lab.noi_dung || itemTitle(kind, it, i), ly_do: lab.ly_do, fix: lab.de_xuat_sua, seg: S.seg[it.segment_id] }] : [];
    return { title: (kind === "slide" ? "Kiểm slide " : "Kiểm câu ") + (i + 1) + "/" + st.draft.items.length, items, counts: st.draft.nhan || [], traces: st.draft.traces || [], draft: st.draft };
  }
  return { title: "Chưa có dữ liệu kiểm chứng ở bước này", items: [], counts: [], traces: [] };
}
function panelBadge(ctx) {
  const bad = ctx.counts.filter((c) => c.nhan === "SAI_NGUON").length, warn = ctx.counts.filter((c) => c.nhan === "THIEU_NGUON").length;
  if (!ctx.counts.length && !ctx.traces.length) return ["grey", "…"];
  return bad ? ["red", String(bad)] : warn ? ["orange", String(warn)] : ["green", "✓"];
}
function agentPanel() {
  const ctx = agentContext(), [col, txt] = panelBadge(ctx), tr = ctx.traces;
  const fab = h("button", { id: "fab", "aria-label": "Mở panel: agent đã kiểm gì ở bước này", onclick: () => { S.panel = !S.panel; render(); } }, "🛡", h("span", { class: "dot " + col }, txt));
  const claims = (ctx.script && ctx.script.claims) || [];
  const segOk = claims.filter((c) => c.segment_id).every((c) => c.nguon);
  const inj = claims.filter((c) => c.nhan === "TU_CHOI").length;
  const costUsd = sum(tr, (t) => t.chi_phi_usd_niem_yet);
  const models = [...new Set(tr.flatMap((t) => t.models || []))];
  const panel = h("aside", { id: "panel", class: S.panel ? "open" : "", role: "dialog", "aria-label": "Agent đã kiểm gì" },
    h("div", { class: "ph" }, h("strong", {}, "Agent verify"), h("button", { "aria-label": "Thu nhỏ panel kiểm chứng", onclick: () => { S.panel = false; render(); } }, "Thu nhỏ")),
    h("div", { class: "pb" },
      h("h2", {}, "Agent đã kiểm gì · " + ctx.title),
      h("h3", {}, "Kết quả mục đang xem"),
      ctx.items.length ? ctx.items.map((x) => h("article", { class: "src" }, h("div", { class: "row" }, badge(x.nhan)), h("p", {}, x.text), x.ly_do ? h("p", { class: "hint" }, x.ly_do) : null,
        x.fix ? h("div", { class: "note info" }, "Gợi ý sửa: " + x.fix) : null, x.seg ? sourceBox(x.seg) : null))
        : h("p", { class: "hint" }, "Chưa có kết quả riêng cho mục này."),
      h("h3", {}, "Quy trình đã chạy"),
      tr.length ? tr.map((t) => h("div", {}, h("strong", {}, t.nhan), h("ul", { class: "steplist" }, (t.cac_buoc || []).map((s) =>
        h("li", { class: s.loi ? "err" : "" }, [s.loai === "model" ? "call_model" : s.loai === "tool" ? s.ten : "ghi chú", s.model ? " · " + s.model : "", s.tokens_in != null && s.loai === "model" ? " · " + s.tokens_in + " vào / " + s.tokens_out + " ra" : "",
          s.latency_s != null ? " · " + s.latency_s + " s" : "", s.loai === "note" ? " · " + s.ten : "", s.loi ? " · lỗi: " + s.loi : ""].join("")))))) : h("p", { class: "hint" }, "Chưa có lượt chạy."),
      h("h3", {}, "Kiểm tra an toàn & nguyên tắc"),
      h("ul", { class: "steplist" },
        ctx.script ? h("li", {}, segOk ? "Mọi mã đoạn được trích đều có thật trong kho" : "Có mã đoạn chưa xác minh được") : null,
        ctx.script ? h("li", {}, inj ? "Đã tách và từ chối " + inj + " câu chứa chỉ dẫn chèn" : "Không phát hiện chỉ dẫn chèn trong kịch bản") : null,
        h("li", {}, "Mọi đầu ra ở trạng thái bản nháp, không tự xuất bản, không gửi học viên")),
      h("h3", {}, "Chi phí & trace"),
      tr.length ? h("dl", { class: "kv" },
        h("dt", {}, "Model"), h("dd", {}, models.join(", ") || "—"),
        h("dt", {}, "Số lần gọi"), h("dd", {}, sum(tr, (t) => t.model_calls) + " model · " + sum(tr, (t) => t.tool_calls) + " công cụ"),
        h("dt", {}, "Token (từ usage)"), h("dd", {}, sum(tr, (t) => t.tokens_in).toLocaleString("vi-VN") + " vào / " + sum(tr, (t) => t.tokens_out).toLocaleString("vi-VN") + " ra"),
        h("dt", {}, "Chi phí"), h("dd", {}, "$" + costUsd.toFixed(4) + " theo giá niêm yết (chi thật qua proxy cao hơn ~6,5 lần)")) : h("p", { class: "hint" }, "—"),
      h("p", { class: "hint", style: "margin-top:12px" }, "Agent chỉ đối chiếu với kho tài liệu gốc và gợi ý. Giảng viên là người quyết định.")));
  return [fab, panel];
}

/* ---------- vẽ ---------- */
function render() {
  const r = route(), app = document.getElementById("app");
  const views = { import: viewImport, script: viewScript, "slide-create": viewSlideCreate, slide: () => viewReview("slide"), quiz: () => viewReview("quiz") };
  const tabOf = { import: "kb", script: "kb", "slide-create": "slide", slide: "slide", quiz: "quiz" }[r] || "kb";
  const tabs = [["kb", "Kịch bản", S.script ? "#/script" : "#/import"], ["slide", "Slide", S.slide ? "#/slide" : "#/slide-create"], ["quiz", "Quiz", "#/quiz"]];
  const scroll = window.scrollY;
  app.replaceChildren(
    h("header", { class: "top" }, h("span", { class: "brand" }, "ScriptGuard"),
      h("nav", { class: "tabs", "aria-label": "Hạng mục kiểm duyệt" }, tabs.map(([k, t, href]) => h("a", { href, class: tabOf === k ? "active" : "" }, t))),
      h("span", { class: "ctx" }, S.script ? "Buổi " + S.script.buoi + " · " + (S.script.stage === "ra_soat" ? "Bản nháp · chưa gửi" : "Đã gửi chờ duyệt") : ""),
      h("span", { class: "spacer" }), h("a", { href: "#/import", class: "ctx" }, "Nhập bản nháp khác")),
    h("main", {}, (views[r] || viewImport)()), ...agentPanel());
  app.classList.toggle("panel-open", S.panel);
  window.scrollTo(0, scroll);
}
window.addEventListener("hashchange", () => { S.err = ""; S.info = ""; render(); });
render();
