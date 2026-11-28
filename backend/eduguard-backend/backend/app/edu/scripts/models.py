"""Lecture script = slides, each with ≤4 key points and narration split into segments A1..An.

A segment is the unit that is checked against the source (gate 1), voiced (one audio clip, so
editing one segment re-synthesises only that clip) and timed on the slide's audio track.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import Field

from app.edu.quiz.schemas import CamelModel

Decision = Literal["chua_quyet", "chap_nhan", "tu_choi_cau", "da_sua"]


class Segment(CamelModel):
    id: str                                    # "A1", "A2"… (unique within the slide)
    text: str
    original_text: Optional[str] = None        # before the teacher's edit
    nhan: str = "THIEU_NGUON"                  # KHOP_NGUON | SAI_NGUON | THIEU_NGUON | TU_CHOI | DAN_DAT
    vai_tro: Literal["noi_dung", "dan_dat"] = "noi_dung"   # dan_dat = lead-in built from slide titles, no new facts
    segment_id: str = ""                       # source chunk id (empty when THIEU / TU_CHOI)
    ly_do: str = ""
    de_xuat_sua: str = ""
    canh_bao_ma: str = ""
    nguon: Optional[Dict[str, Any]] = None     # the cited chunk, for the side panel
    quyet_dinh: Decision = "chua_quyet"
    voice: Optional[Dict[str, Any]] = None     # {url, duration, start, end, cached, timing_source}


class ScriptSlide(CamelModel):
    index: int
    tieu_de: str
    y_chinh: List[str] = Field(default_factory=list)
    doan: List[Segment] = Field(default_factory=list)
    image_ids: List[str] = Field(default_factory=list)   # figures from the source doc to show on this slide
    table_ids: List[str] = Field(default_factory=list)
    layout: Optional[str] = None               # see app/edu/slide_frame.py (bullets, image_text, table, comparison,
                                               # process, key_fact, agenda, summary, check)
    phan: str = ""                             # section label shown above the title
    extra: Dict[str, Any] = Field(default_factory=dict)   # layout data: cot / buoc / nhan_manh / cau_hoi+dap_an
    audio: Optional[Dict[str, Any]] = None     # concatenated slide track {url, duration, markers[]}


class Script(CamelModel):
    id: str
    doc_id: str
    title: str
    origin: Literal["pasted", "generated"] = "pasted"
    status: Literal["nhap", "cho_duyet"] = "nhap"
    slides: List[ScriptSlide] = Field(default_factory=list)
    created_at: float = 0
    updated_at: float = 0
    owner: Optional[str] = None
    trace: Optional[Dict[str, Any]] = None

    def segments(self):
        for s in self.slides:
            for seg in s.doan:
                yield s, seg


class CreateScriptRequest(CamelModel):
    doc_id: str
    title: Optional[str] = None
    noi_dung: Optional[str] = None             # paste mode: the draft script text
    chu_de: Optional[str] = None               # generate mode: topic / focus inside the document
    so_slide: int = Field(6, ge=1, le=30)
    doan_moi_slide: int = Field(3, ge=1, le=6)
    khung: Literal["bai_giang", "gon"] = "bai_giang"   # lesson arc (agenda/summary/check) or content only
    language: str = "Vietnamese"


class SegmentDecision(CamelModel):
    slide: int
    segment: str                               # "A2"
    action: Literal["accept", "reject", "edit", "reset"]
    text: Optional[str] = None                 # required for edit


class DecisionsRequest(CamelModel):
    decisions: List[SegmentDecision]
