"""Offline exporter tests; opt in to the real TTS service with RUN_TTS_TESTS=1."""

import asyncio
from html import escape
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from fpdf import FPDF
from codebase.exporters import export_quiz_pdf, render_slides, synthesize_voice


class ExporterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name) / "output"

    def test_pdf_files_and_separate_answer_content(self):
        quiz = [{"de": "Thủ đô Việt Nam ở đâu?", "A": "Hà Nội", "B": "Huế",
                 "C": "Đà Nẵng", "D": "Cần Thơ", "dap_an": "A",
                 "giai_thich": "Giải thích bí mật: Hà Nội là thủ đô.", "segment_id": "nguon-bi-mat-42"}]
        captured = {}
        original = FPDF.multi_cell

        def capture(pdf, *args, **kwargs):
            captured.setdefault(id(pdf), []).append(kwargs.get("text", ""))
            return original(pdf, *args, **kwargs)

        with patch.object(FPDF, "multi_cell", capture):
            paths = export_quiz_pdf(quiz, str(self.directory), "Bài kiểm tra tiếng Việt")
        for path in paths.values():
            self.assertGreater(Path(path).stat().st_size, 0)
            self.assertTrue(Path(path).read_bytes().startswith(b"%PDF"))
        # Inspect actual rendering arguments: no extra PDF extraction dependency.
        exam, answers = ("\n".join(lines) for lines in captured.values())
        self.assertIn(quiz[0]["de"], exam)
        for letter in "ABCD":
            self.assertIn(f"{letter}. {quiz[0][letter]}", exam)
        for secret in ("Đáp án", "Giải thích", quiz[0]["giai_thich"], quiz[0]["segment_id"]):
            self.assertNotIn(secret, exam)
        self.assertIn("Đáp án: A", answers)
        self.assertIn(quiz[0]["giai_thich"], answers)
        self.assertIn(quiz[0]["segment_id"], answers)

    def test_missing_unicode_font(self):
        with patch("codebase.exporters.Path.is_file", return_value=False):
            with self.assertRaisesRegex(RuntimeError, "Unicode TTF"):
                export_quiz_pdf([], str(self.directory))

    def test_html_escapes_all_fields_and_relative_audio(self):
        malicious = '<script>alert(1)</script> & "quoted"'
        slide = {"tieu_de": malicious, "y_chinh": [malicious],
                 "loi_thuyet_trinh": malicious, "segment_id": malicious}
        audio = Path(self.temp.name) / 'voice & "one".mp3'
        html = Path(render_slides([slide, slide], str(self.directory), malicious, {1: str(audio)})).read_text(encoding="utf-8")
        self.assertNotIn("<script>alert(1)</script>", html)
        self.assertEqual(html.count(escape(malicious)), 10)
        self.assertIn('src="../voice%20%26%20%22one%22.mp3"', html)
        self.assertEqual(html.count("<audio controls"), 1)
        self.assertIn("<details>", html)
        self.assertIn('class="slide" hidden', html)
        self.assertIn("ArrowLeft", html)
        self.assertIn("ArrowRight", html)

    def test_empty_slides(self):
        path = render_slides([], str(self.directory))
        self.assertTrue(Path(path).is_file())

    def test_invalid_voice_and_empty_text(self):
        with self.assertRaises(ValueError):
            synthesize_voice(1, "Xin chào", str(self.directory), "unknown")
        for text in ("", " \n\t"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                synthesize_voice(1, text, str(self.directory))
        self.assertFalse(self.directory.exists())

    def test_tts_mocked_with_and_without_running_loop(self):
        threads = []

        async def save(filename):
            threads.append(threading.get_ident())
            Path(filename).write_bytes(b"mock mp3")

        with patch("edge_tts.Communicate") as communicate:
            communicate.return_value.save = save
            path = synthesize_voice(1, "Xin chào", str(self.directory))

            async def running():
                return synthesize_voice(2, "Xin chào", str(self.directory), "vi-VN-NamMinhNeural")

            other = asyncio.run(running())
            self.assertEqual(Path(path).name, "slide_1.mp3")
            self.assertEqual(Path(other).read_bytes(), b"mock mp3")
            self.assertEqual(threads[0], threading.get_ident())
            self.assertNotEqual(threads[1], threading.get_ident())
            self.assertEqual(communicate.call_args.args, ("Xin chào", "vi-VN-NamMinhNeural"))

    def test_tts_service_failure(self):
        async def fail(filename):
            raise OSError("service unavailable")

        with patch("edge_tts.Communicate") as communicate:
            communicate.return_value.save = fail
            with self.assertRaisesRegex(RuntimeError, "service unavailable"):
                synthesize_voice(1, "Xin chào", str(self.directory))

    @unittest.skipUnless(os.environ.get("RUN_TTS_TESTS") == "1", "Set RUN_TTS_TESTS=1 for real TTS")
    def test_real_tts(self):
        path = synthesize_voice(1, "Xin chào Việt Nam.", str(self.directory))
        self.assertGreater(Path(path).stat().st_size, 0)


if __name__ == "__main__":
    unittest.main()
