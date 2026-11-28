"""Slide framework: deterministic normalisation of model-proposed slides + per-frame HTML rendering."""
from types import SimpleNamespace as NS

from app.edu import html_deck, slide_frame
from app.edu.scripts.models import Script, ScriptSlide, Segment

IMAGES = {"img1": NS(kind="figure", mime="image/png"), "scan": NS(kind="page_scan", mime="image/png")}
TABLES = {"tbl1": object()}
CHUNKS = {"C1": "Độ chính xác đạt 92,5% sau khi thêm truy xuất. RAG giảm bịa đặt."}


def norm(**raw):
    raw.setdefault("tieu_de", "T")
    raw.setdefault("doan", [{"text": "Lời đọc.", "segment_id": "C1"}])
    return slide_frame.normalize(raw, images=IMAGES, tables=TABLES, chunk_text=CHUNKS)


def test_layout_needs_its_data_else_falls_back():
    assert norm(layout="table", table_ids=["tbl404"])["layout"] == "bullets"          # invented table id
    assert norm(layout="image_text", image_ids=["scan"])["layout"] == "bullets"        # page scans are not figures
    assert norm(layout="image_text", image_ids=["img1"])["image_ids"] == ["img1"]
    assert norm(layout="comparison", cot=[{"ten": "A", "y": ["x"]}])["layout"] == "bullets"
    assert norm(layout="process", buoc=[{"ten": "1"}, {"ten": "2"}])["layout"] == "bullets"
    ok = norm(layout="process", buoc=[{"ten": "a"}, {"ten": "b"}, {"ten": "c"}])
    assert ok["layout"] == "process" and len(ok["extra"]["buoc"]) == 3
    assert norm(layout="weird", table_ids=["tbl1"])["layout"] == "table"               # inferred from content


def test_key_fact_must_be_in_cited_source():
    assert norm(layout="key_fact", nhan_manh={"gia_tri": "92,5%"})["layout"] == "key_fact"
    assert norm(layout="key_fact", nhan_manh={"gia_tri": "97%"})["layout"] == "bullets"     # number not in source
    uncited = norm(layout="key_fact", nhan_manh={"gia_tri": "92,5%"}, doan=[{"text": "x", "segment_id": "C9"}])
    assert uncited["layout"] == "bullets"


def test_limits_points_and_words():
    s = norm(y_chinh=[" ".join(["từ"] * 30)] + ["b", "c", "d", "e", "f"])
    assert len(s["y_chinh"]) == 4 and s["y_chinh"][0].endswith("…") and len(s["y_chinh"][0].split()) == 14


def test_outline_lesson_arc_and_compact():
    content = [norm(tieu_de="Một"), norm(tieu_de="Hai")]
    deck = {"tom_tat": [{"text": "RAG giảm bịa đặt.", "segment_id": "C1"}],
            "cau_hoi_nhanh": {"cau_hoi": "RAG giảm điều gì?", "dap_an": "Bịa đặt", "segment_id": "C1"}}
    full = slide_frame.outline("bai_giang", content, deck, "T")
    assert [s["layout"] for s in full] == ["agenda", "bullets", "bullets", "summary", "check"]
    assert full[0]["doan"] == [] and "Một; Hai" in full[0]["dan_dat"][0]            # agenda: titles only, no facts
    assert full[-1]["doan"] == ["Đáp án: Bịa đặt"]                                   # the answer is checked
    assert [s["layout"] for s in slide_frame.outline("gon", content, deck, "T")] == ["bullets", "bullets"]


def test_html_renders_each_frame_escaped():
    seg = lambda i, t, **k: Segment(id=i, text=t, nhan="KHOP_NGUON", **k)  # noqa: E731
    slides = [
        ScriptSlide(index=0, tieu_de="Nội dung chính", layout="agenda", y_chinh=["<b>x</b>"],
                    doan=[seg("A1", "Bài gồm", vai_tro="dan_dat")]),
        ScriptSlide(index=1, tieu_de="So sánh", layout="comparison", phan="Phần 1",
                    extra={"cot": [{"ten": "A", "y": ["a"]}, {"ten": "B", "y": ["<script>"]}]}, doan=[seg("A1", "x")]),
        ScriptSlide(index=2, tieu_de="Quy trình", layout="process",
                    extra={"buoc": [{"ten": s, "mo_ta": ""} for s in "abc"]}, doan=[seg("A1", "x")]),
        ScriptSlide(index=3, tieu_de="Câu hỏi nhanh", layout="check", extra={"cau_hoi": "Q?", "dap_an": "Ans"},
                    doan=[seg("A1", "Q?", vai_tro="dan_dat"), seg("A2", "Đáp án: Ans")]),
    ]
    html = html_deck.render(Script(id="scr_t", doc_id="d", title="T", slides=slides), None)
    assert 'class="agenda"' in html and 'class="cols"' in html and 'class="steps"' in html and 'class="ans"' in html
    assert "<script>\"" not in html and "&lt;script&gt;" in html and "&lt;b&gt;x&lt;/b&gt;" in html
    assert "<b>2</b> / 6" in html                                  # cover + 4 + end, footer numbering


def test_string_points_logo_filter_and_step_names():
    assert norm(y_chinh="Một ý duy nhất")["y_chinh"] == ["Một ý duy nhất"]        # not split into characters
    logo = NS(kind="figure", mime="image/png", bbox=[498, 55, 558, 127], width_px=239, height_px=298)
    fig = NS(kind="figure", mime="image/png", bbox=[122, 165, 473, 326], width_px=1461, height_px=672)
    assert not slide_frame.is_figure(logo) and slide_frame.is_figure(fig)
    s = slide_frame.normalize({"tieu_de": "T", "layout": "image_text", "image_ids": ["logo"], "doan": ["x"]},
                              images={"logo": logo}, tables={}, chunk_text={})
    assert s["layout"] == "bullets" and s["image_ids"] == []
    p = norm(layout="process", buoc=[{"ten": f"Bước {i}", "mo_ta": f"Làm việc {i}"} for i in range(1, 4)])
    assert [b["ten"] for b in p["extra"]["buoc"]] == ["Làm việc 1", "Làm việc 2", "Làm việc 3"]
