"""Test setup: isolated SQLite DB + data dir, fake LLM, silent TTS. Never calls a real API."""
import base64
import os
import sys
import tempfile

_TMP = tempfile.mkdtemp(prefix="eduguard-test-")
os.environ.update({
    "DATABASE_URL": f"sqlite:///{_TMP}/test.db",
    "EDU_DATA_DIR": os.path.join(_TMP, "edu"),
    "EDU_PUBLIC_BASE_URL": "",
    "TTS_PROVIDER": "silent",
    "ANTHROPIC_API_KEY": "", "GEMINI_API_KEY": "", "OPENAI_API_KEY": "", "GROQ_API_KEYS": "", "OPENROUTER_API_KEY": "",
    "BILLING_ENFORCE": "false",
    "EDUGUARD_ENV_FILE": "",          # never read the developer .env (real keys) in tests
    "FERNET_KEY": base64.b64encode(os.urandom(32)).decode(),
})
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
