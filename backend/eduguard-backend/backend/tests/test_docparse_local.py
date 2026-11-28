import asyncio

from tests.fixtures import make_pdf, make_pptx


def _ingest(data, name):
    from app.edu import docparse
    return asyncio.run(docparse.ingest(data, name))


def test_pdf_local_text_table_image_headers():
    doc = _ingest(make_pdf(), "bai7.pdf")
    assert doc.engine == "local-pymupdf"
    kinds = [b.type for b in doc.blocks]
    assert "heading" in kinds and "table" in kinds and "image" in kinds
    tbl = next(b.table for b in doc.blocks if b.type == "table")
    assert tbl.n_rows == 3 and tbl.n_cols == 2 and "500" in tbl.markdown
    # header line and page numbers dropped
    assert not any("tài liệu nội bộ" in b.text for b in doc.blocks)
    # table text not duplicated as paragraph
    assert sum("Gia tri" in b.text for b in doc.blocks) == 1
    img = next(iter(doc.images.values()))
    assert img.page == 1 and img.bbox and img.kind == "figure"
    assert img.alt and img.alt.startswith("Hinh 1")          # caption attached
    assert all(b.bbox for b in doc.blocks if b.page == 1)
    assert doc.chunks and all(c.pages for c in doc.chunks)
    assert doc.meta["pages"] == 3


def test_pptx_local_notes_table_picture():
    doc = _ingest(make_pptx(), "slides.pptx")
    assert doc.engine == "local-python-pptx"
    heads = [b.text for b in doc.blocks if b.type == "heading"]
    assert heads == ["Temperature", "Tham so lab"]
    notes = [b for b in doc.blocks if b.source == "notes"]
    assert notes and "khong lam on dinh" in notes[0].text
    lvl = [b for b in doc.blocks if b.type == "list_item" and b.level == 1]
    assert lvl and lvl[0].text.startswith("Temperature cao")
    assert doc.tables and next(iter(doc.tables.values())).n_rows == 2
    assert len(doc.images) == 1 and next(iter(doc.images.values())).kind == "slide_picture"
    assert "Ghi chú người nói" in doc.markdown
