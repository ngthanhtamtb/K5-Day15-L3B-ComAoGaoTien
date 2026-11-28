"""Source verification: label each statement KHOP_NGUON / SAI_NGUON / THIEU_NGUON / TU_CHOI.

Ported from the hackathon prototype (codebase/agent.py, 6 eval runs) with one structural fix:
the model labels statements BY INDEX instead of re-quoting them, so it cannot invent a claim
that is not in the input (the "khẳng định lạc đề" failure seen in eval runs B05/B13).

Rules enforced in code, not trusted to the model:
  * a statement carrying an injected instruction is TU_CHOI without any model call
  * no retrieved passage scores above zero  -> THIEU_NGUON without any model call
  * segment_id must be one of the passages shown to the model, otherwise -> THIEU_NGUON
"""
from .service import (INJECT, LABELS, check_items, check_quiz_question, has_injection)  # noqa: F401
