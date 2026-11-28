import asyncio
import os

import pytest

SAMPLE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scripts", "sample_exam.docx")


@pytest.mark.skipif(not os.path.exists(SAMPLE), reason="sample_exam.docx not present")
def test_sample_exam_still_extracts_five_questions_with_answers():
    from app.edu import docparse
    from app.edu.quiz import service
    with open(SAMPLE, "rb") as fh:
        doc = asyncio.run(docparse.ingest(fh.read(), "sample_exam.docx"))
    qs = service.extract(doc.doc_id)
    assert len(qs.questions) == 5
    mcq = [q for q in qs.questions if q.type == "mcq"]
    assert mcq and all(q.correct_key for q in mcq)
    assert qs.status == "nhap" and all(q.decision == "chua_quyet" for q in qs.questions)
