"""Test offline cho: thử lại 403 rate limit, nạp tài liệu (tools + API), tuỳ chọn slide, chữ ký ổn định.
Chạy: python -m unittest tests.test_features -v   (không gọi model, không tốn tiền)"""
import base64
import io
import json
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "codebase"))
sys.path.insert(0, str(ROOT / "eval"))

import ai          # noqa: E402
import api         # noqa: E402
import exporters   # noqa: E402
import stability   # noqa: E402
import tools       # noqa: E402

DOC = ("Giới thiệu về chương trình học. " * 12 + "\n\n" + "Phần hai nói về cách chấm điểm bài tập lớn. " * 12).encode("utf-8")


class RateLimitRetry(unittest.TestCase):
    def _http_error(self, code, body):
        return urllib.error.HTTPError("http://x", code, "err", {}, io.BytesIO(body.encode()))

    def test_403_rate_limit_retried_then_ok(self):
        ok = io.BytesIO(json.dumps({"ok": 1}).encode())
        ok.__enter__ = lambda s=ok: ok
        ok.__exit__ = lambda *a: False
        calls = [self._http_error(403, '{"error":{"type":"rate_limit_error","message":"Try again in 3 seconds"}}'), ok]

        def fake(req, timeout=0):
            r = calls.pop(0)
            if isinstance(r, Exception):
                raise r
            return r
        slept = []
        with patch("ai.urllib.request.urlopen", fake), patch("ai.time.sleep", slept.append):
            self.assertEqual(ai.post_json("http://x", {}, {}), {"ok": 1})
        self.assertEqual(slept, [4.0])          # chờ đúng 3 + 1 giây proxy yêu cầu

    def test_403_other_not_retried(self):
        def fake(req, timeout=0):
            raise self._http_error(403, '{"error":"forbidden"}')
        with patch("ai.urllib.request.urlopen", fake), patch("ai.time.sleep"):
            with self.assertRaises(RuntimeError):
                ai.post_json("http://x", {}, {})


class UploadFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = patch.object(tools, "UPLOADS_PATH", os.path.join(self.tmp.name, "u", "segments.json"))
        p.start()
        self.addCleanup(p.stop)
        tools._cache.clear()
        self.addCleanup(tools._cache.clear)

    def _upload(self, **kw):
        body = dict(filename="giao-trinh.txt", content_b64=base64.b64encode(DOC).decode(), title="Giáo trình thử")
        body.update(kw)
        return api.kho_upload(api.UploadBody(**body))

    def test_upload_adds_searchable_segments_and_delete_removes(self):
        before = len(tools.load_segments())
        r = self._upload()
        self.assertEqual(r["buoi"], 10)
        self.assertTrue(r["doan"][0].startswith("D10-S"))
        self.assertEqual(len(tools.load_segments()), before + r["so_doan"])
        self.assertIn(10, tools.available_sessions())
        hits = tools.search_sources("chấm điểm bài tập lớn", buoi=10)
        self.assertTrue(hits and hits[0]["segment_id"].startswith("D10-"))
        self.assertEqual(tools.get_segment(r["doan"][0])["full_text"][:12], "Giới thiệu v")
        kho = [k for k in api.kho() if k["buoi"] == 10][0]
        self.assertTrue(kho["tai_len"])
        self.assertEqual(self._upload(title="Tài liệu hai")["buoi"], 11)     # buổi trống tiếp theo
        self.assertEqual(api.kho_delete(10)["da_xoa"], r["so_doan"])
        self.assertNotIn(10, tools.available_sessions())

    def test_no_uploads_env_keeps_original_corpus(self):
        self._upload()
        with patch.dict(os.environ, {"A3_NO_UPLOADS": "1"}):
            tools._cache.clear()
            self.assertEqual(len(tools.load_segments()), 14)
            self.assertEqual(tools.available_sessions(), [1, 4, 7])

    def test_bad_inputs_rejected(self):
        from fastapi import HTTPException
        for kw in (dict(filename="a.exe"), dict(content_b64="@@@"), dict(buoi=3)):
            with self.assertRaises(HTTPException) as cm:
                self._upload(**kw)
            self.assertEqual(cm.exception.status_code, 422)
        with self.assertRaises(HTTPException) as cm:
            api.kho_delete(7)
        self.assertEqual(cm.exception.status_code, 403)


class SlideOptions(unittest.TestCase):
    SL = [{"tieu_de": "T", "y_chinh": ["a"], "segment_id": "D01-S01", "loi_thuyet_trinh": "LOI-NOI"}]

    def render(self, options=None):
        with tempfile.TemporaryDirectory() as d:
            return Path(exporters.render_slides(self.SL, d, "x", None, options)).read_text(encoding="utf-8")

    def test_default_unchanged(self):
        html = self.render()
        self.assertIn("LOI-NOI", html)
        self.assertNotIn("aspect-ratio", html)

    def test_options_applied(self):
        html = self.render({"mau": "Tối giản", "ty_le": "4:3", "ghi_chu": False})
        self.assertNotIn("LOI-NOI", html)
        self.assertIn("aspect-ratio:4/3", html)
        self.assertIn("border-radius:0", html)
        self.assertIn("aspect-ratio:16/9", self.render({"ty_le": "16:9"}))
        self.assertNotIn("aspect-ratio", self.render({"ty_le": "9:99"}))      # giá trị lạ bị bỏ qua


class Signature(unittest.TestCase):
    def test_signature(self):
        out = "1) SAI_NGUON · D04-Q01\n2) KHOP_NGUON · D04-S02"
        self.assertEqual(stability.signature("[DUYET_QUIZ] x", out), ("SAI_NGUON>KHOP_NGUON", ("D04-Q01", "D04-S02")))
        self.assertEqual(stability.signature("[TAO_QUIZ] x", out), ("", ("D04-Q01", "D04-S02")))


class SlideVoiceEndpoint(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p_dir = patch.object(api, "DRAFT_DIR", self.tmp.name)
        p_state = patch.object(api, "STATE_FILE", os.path.join(self.tmp.name, "_state.json"))
        p_dir.start()
        p_state.start()
        self.addCleanup(p_dir.stop)
        self.addCleanup(p_state.stop)
        self.did = "draft-voice01"
        api.DRAFTS[self.did] = {
            "draft_id": self.did, "kind": "slide", "buoi": 1, "chu_de": "temperature",
            "options": {"voice": "vi-VN-HoaiMyNeural", "rate": "+0%"},
            "items": [
                {"tieu_de": "Slide 1", "y_chinh": ["Temperature thấp giúp ổn định"], "loi_thuyet_trinh": "Temperature thấp làm phân bố nhọn hơn. [D01-S02]", "segment_id": "D01-S02"},
                {"tieu_de": "Slide 2", "y_chinh": ["Context window 128K"], "loi_thuyet_trinh": "Context window gồm cả đầu vào và đầu ra.", "segment_id": "D01-S04"},
            ],
            "nhan": [], "stage": "cong_1", "status": "cho_duyet", "files": {}, "traces": [],
        }
        self.addCleanup(lambda: api.DRAFTS.pop(self.did, None))

    def test_synthesize_single_slide_and_switch_voice(self):
        calls = []

        def fake_tts(slide_id, text, out_dir, voice="vi-VN-HoaiMyNeural", rate="+0%"):
            calls.append((slide_id, text, voice, rate))
            out = Path(out_dir) / f"slide_{slide_id}.mp3"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_bytes(b"ID3-mock")
            return str(out)

        with patch.object(exporters, "synthesize_voice", fake_tts):
            res = api.synthesize_draft_voice(
                self.did,
                api.VoiceBody(slide_index=1, voice="vi-VN-NamMinhNeural", rate="+15%", loi_thuyet_trinh="Câu một mới. Câu hai mới.", recheck=False),
            )
        d = res["draft"]
        self.assertEqual(d["options"]["voice"], "vi-VN-NamMinhNeural")
        self.assertEqual(d["options"]["rate"], "+15%")
        self.assertIn("audio_1", d["files"])
        self.assertNotIn("audio_2", d["files"])
        self.assertEqual(len(d["voice_segments"]["1"]), 2)
        self.assertEqual(d["voice_segments"]["1"][0]["id"], "A1")
        self.assertEqual(calls, [(1, "Câu một mới. Câu hai mới.", "vi-VN-NamMinhNeural", "+15%")])

    def test_clean_tts_strips_segment_brackets(self):
        self.assertEqual(exporters._clean_tts_text("Nhiệt độ thấp ổn định hơn [D01-S02]."), "Nhiệt độ thấp ổn định hơn .")
        self.assertEqual(exporters._clean_tts_text("Xin chào"), "Xin chào")


if __name__ == "__main__":
    unittest.main()
