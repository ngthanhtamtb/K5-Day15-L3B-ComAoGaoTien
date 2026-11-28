"""Layout-preserving document model.

Every parser (docx native, docling, remote) produces a ParsedDocument: an ordered list of
blocks where images and tables stay at the exact position they had in the source file.
Quiz extraction, RAG chunking and slide generation all read from this one structure.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

BlockType = Literal["heading", "paragraph", "list_item", "table", "image", "equation", "page_break"]


class Span(BaseModel):
    """A run of text with the formatting that exams often use to mark answers."""
    text: str
    bold: bool = False
    italic: bool = False
    underline: bool = False
    color: Optional[str] = None        # hex, e.g. "FF0000"
    highlight: Optional[str] = None    # e.g. "yellow"
    image_id: Optional[str] = None     # inline image placed at this position
    equation: Optional[str] = None     # linearised OMML equation


class DocImage(BaseModel):
    id: str
    path: str                          # path on disk (relative to EDU_DATA_DIR)
    url: str                           # served URL
    mime: str
    width_px: Optional[int] = None
    height_px: Optional[int] = None
    alt: Optional[str] = None
    converted_from: Optional[str] = None  # e.g. "wmf" when we rasterised a MathType/WMF image
    page: Optional[int] = None
    bbox: Optional[List[float]] = None    # [x0, y0, x1, y1] in points on that page
    caption: Optional[str] = None         # vision-model description (EDU_IMAGE_CAPTIONS) — searchable
    kind: Optional[str] = None            # "figure" | "page_scan" | "slide_picture"


class TableCell(BaseModel):
    text: str
    row: int
    col: int
    rowspan: int = 1
    colspan: int = 1
    blocks: List["Block"] = Field(default_factory=list)


class DocTable(BaseModel):
    id: str
    n_rows: int
    n_cols: int
    cells: List[TableCell]
    markdown: str
    html: str


class Block(BaseModel):
    id: str
    type: BlockType
    order: int
    text: str = ""
    level: Optional[int] = None        # heading level or list indent level
    list_label: Optional[str] = None   # rendered auto-numbering, e.g. "Câu 3." or "B."
    style: Optional[str] = None
    spans: List[Span] = Field(default_factory=list)
    image_ids: List[str] = Field(default_factory=list)
    table: Optional[DocTable] = None
    page: Optional[int] = None
    in_table: Optional[str] = None     # table id when the block lives inside a cell
    bbox: Optional[List[float]] = None  # [x0, y0, x1, y1] in points (PDF/PPTX) — lets the UI highlight the source
    source: Optional[str] = None       # "text" | "ocr" | "notes" (PPTX speaker notes)

    @property
    def full_text(self) -> str:
        return f"{self.list_label} {self.text}".strip() if self.list_label else self.text


TableCell.model_rebuild()


class Chunk(BaseModel):
    """Retrieval unit used for RAG and for source grounding in the Eval panel."""
    id: str                            # e.g. "D3F2-C004"
    heading_path: List[str] = Field(default_factory=list)
    text: str
    block_ids: List[str] = Field(default_factory=list)
    image_ids: List[str] = Field(default_factory=list)
    table_ids: List[str] = Field(default_factory=list)
    pages: List[int] = Field(default_factory=list)


class ParsedDocument(BaseModel):
    doc_id: str
    filename: str
    engine: str
    blocks: List[Block]
    images: Dict[str, DocImage] = Field(default_factory=dict)
    tables: Dict[str, DocTable] = Field(default_factory=dict)
    chunks: List[Chunk] = Field(default_factory=list)
    markdown: str = ""
    meta: Dict[str, Any] = Field(default_factory=dict)

    def iter_blocks(self, include_table_cells: bool = True):
        """Depth-first walk including blocks nested in table cells, in reading order."""
        for b in self.blocks:
            yield b
            if include_table_cells and b.table:
                for cell in b.table.cells:
                    for cb in cell.blocks:
                        yield cb
