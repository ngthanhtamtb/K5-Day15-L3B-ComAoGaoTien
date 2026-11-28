from pydantic import field_validator
from pydantic_settings import BaseSettings
from typing import Optional, List


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    # SQLite for dev/test; PostgreSQL in prod: postgresql://user:password@localhost/smartppt
    DATABASE_URL: str = "sqlite:///./data/eduguard.db"

    SECRET_KEY: str = "change-this-secret-key-in-production-use-env-file"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 3
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    GEMINI_API_KEY: str = ""  # Set this in .env file
    PROMPT_TEMPERATURE: float = 0.3
    PROMPT_TOP_K: int = 1
    PROMPT_TOP_P: float = 0.9
    PROMPT_MAX_OUTPUT_TOKENS: int = 25000
    GEMINI_API_URL: str = "https://generativelanguage.googleapis.com/v1beta/models"
    # Legacy RAGslides remote extractor. Empty by default: documents are parsed locally and
    # never leave this server unless you set this AND EDU_PDF_ENGINE=remote.
    EXTRACT_DOC_API_URL: str = ""

    MAX_FILE_SIZE: Optional[int] = 10 * 1024 * 1024  # 10MB
    TEMPLATE_DIR: Optional[str] = "data/templates"
    UPLOAD_TEMPLATES_DIR: Optional[str] = "data/uploads/templates"
    UPLOAD_PAGE_DIR: Optional[str] = "data/uploads/pages"
    UPLOAD_DIRS: List[str] = [
        "data/uploads/media", "data/uploads/templates", "data/uploads/pages",
        "data/uploads/presentations", "data/uploads/avatars",
    ]

    IMAGES_DIR: str = "data/images/templates"
    SUPPORTED_EXTENSIONS: set = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.svg'}
    ALLOWED_FILE_TYPES: dict = {
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".md": "text/markdown",
        ".csv": "text/csv",
        ".txt": "text/plain",
    }

    FERNET_KEY: str = ""

    # ===== EduGuard extensions (app/edu) =====
    EDU_DATA_DIR: str = "data/edu"              # served under /static/edu/...
    EDU_PUBLIC_BASE_URL: str = ""               # e.g. http://localhost:8077 ; empty = relative URLs
    EDU_MAX_UPLOAD_MB: int = 50
    EDU_UI_DIR: str = "../../../ui"             # web UI served at /ui (repo root ui/); "" to disable

    # Document parsing: docx -> native parser; pdf/pptx ->
    #   "local"  PyMuPDF + pdfplumber + python-pptx (text blocks with bbox, tables, images) — default
    #   "docling" local layout model (heavy, optional) · "auto" docling if installed else local
    #   "remote" EXTRACT_DOC_API_URL (sends the file to that server — opt-in only)
    EDU_PDF_ENGINE: str = "local"
    EDU_OCR_ENABLED: bool = False               # OCR scanned PDF pages with the "vision" LLM route
    EDU_IMAGE_CAPTIONS: bool = False            # describe figures with the "vision" route (searchable)
    EDU_MIN_IMAGE_PX: int = 48                  # skip icons/bullets smaller than this

    # ===== LLM providers (app/core/llm). Routing per task lives in LLM_ROUTES_FILE.
    LLM_ROUTES_FILE: str = "config/llm.yaml"
    LLM_TIMEOUT: float = 120.0
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_BASE_URL: str = "https://api.anthropic.com"
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    GROQ_API_KEYS: str = ""                     # comma-separated, rotated on 429/5xx
    GROQ_API_KEY: str = ""                      # BE_Zentus style single / numbered keys are merged in too
    GROQ_API_KEY_1: str = ""
    GROQ_API_KEY_2: str = ""
    GROQ_API_KEY_3: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"  # used by "groq:{GROQ_MODEL}" entries in config/llm.yaml
    GEMINI_MODEL: str = "gemini-2.5-flash"      # used by "gemini:{GEMINI_MODEL}"
    OPENROUTER_API_KEY: str = ""
    OLLAMA_BASE_URL: str = "http://localhost:11434/v1"

    # Quiz engine: "llm" (provider router, task "quiz") | "zentus" (external fn) | "gemini" (alias of llm)
    QUIZ_ENGINE: str = "llm"
    QUIZ_MODEL: str = "gemini-2.5-flash"        # used only by legacy RAGslides Gemini paths

    # ===== Users & plans (framework only — not enforced unless BILLING_ENFORCE=true)
    BILLING_ENFORCE: bool = False
    PLANS_FILE: str = "config/plans.yaml"
    ADMIN_EMAILS: str = "admin@smartppt.com"    # comma-separated; also users with role=admin
    ZENTUS_PATH: str = ""                       # e.g. E:/Python_Project/VinAI_Lab/BE_Zentus
    ZENTUS_GENERATE_FN: str = ""                # "package.module:function" for quiz generation
    ZENTUS_EVALUATE_FN: str = ""                # optional "package.module:function" for quiz eval

    # Text-to-speech: "silent" (dev, no API) | "http" (generic REST API, configured below)
    TTS_PROVIDER: str = "silent"
    TTS_API_URL: str = ""
    TTS_API_KEY: str = ""
    TTS_API_KEY_HEADER: str = "Authorization"   # header name
    TTS_API_KEY_PREFIX: str = "Bearer "         # header value prefix
    TTS_REQUEST_TEMPLATE: str = '{"text": "{text}", "voice": "{voice}", "speed": {speed}}'
    TTS_RESPONSE_TYPE: str = "binary"           # binary | json_base64 | json_url
    TTS_RESPONSE_FIELD: str = "audio"           # dotted path for json_* modes, e.g. data.audio_url
    TTS_AUDIO_EXT: str = "mp3"
    TTS_DEFAULT_VOICE: str = "default"
    TTS_MAX_CHARS: int = 1500                   # long scripts are split by sentence
    TTS_TIMEOUT: float = 120.0
    # Job-style APIs (submit -> poll). TTS_MODE=job uses the fields below; sync uses TTS_API_URL.
    TTS_MODE: str = "sync"                      # sync | job
    TTS_SUBMIT_URL: str = ""
    TTS_POLL_URL: str = ""                      # template, e.g. https://api.x/tts/jobs/{job_id}
    TTS_JOB_ID_FIELD: str = "job_id"            # dotted path in the submit response
    TTS_STATUS_FIELD: str = "status"            # dotted path in the poll response
    TTS_DONE_VALUES: str = "done,completed,succeeded,success"
    TTS_FAILED_VALUES: str = "failed,error,cancelled"
    TTS_TIMINGS_FIELD: str = ""                 # dotted path to word/sentence timings, if the API returns them
    TTS_DURATION_FIELD: str = ""                # dotted path to duration (seconds), if returned
    TTS_POLL_INTERVAL: float = 1.0              # first poll delay; doubles up to TTS_POLL_MAX_INTERVAL
    TTS_POLL_MAX_INTERVAL: float = 8.0
    TTS_POLL_MAX_WAIT: float = 300.0
    # Limits (fill from the provider's docs) and pricing used for estimates + usage tracking
    TTS_RPM: int = 60                           # requests per minute (token bucket)
    TTS_CONCURRENCY: int = 2                    # simultaneous requests / jobs
    TTS_MAX_RETRIES: int = 3                    # on 429 / 5xx / timeouts
    TTS_PRICE_UNIT: str = "char"                # char | second | request
    TTS_PRICE_PER_UNIT: float = 0.0             # 0 = unknown yet
    TTS_PRICE_CURRENCY: str = "VND"
    TTS_CHARS_PER_SECOND: float = 14.0          # Vietnamese speech ≈ 14 chars/s at 1.0× (estimate only)
    # Job APIs that serve audio from their own (authenticated) endpoint, e.g. .../v1/jobs/{job_id}/audio.
    # When set, audio is downloaded from here WITH the API key instead of from TTS_RESPONSE_FIELD.
    TTS_AUDIO_URL: str = ""
    TTS_VOICES_URL: str = ""                    # GET list of voices (with the API key)
    TTS_VOICES_FIELD: str = ""                  # dotted path to the list in that response ("" = top level)

    SMTP_HOST: Optional[str] = None
    SMTP_PORT: Optional[int] = None
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None

    @field_validator("SMTP_PORT", "MAX_FILE_SIZE", mode="before")
    @classmethod
    def _empty_is_none(cls, v):
        # ".env" lines like "SMTP_PORT=" mean "not set", not an invalid integer
        return None if isinstance(v, str) and not v.strip() else v

    class Config:
        env_file = ".env"
        # .env files are shared with other services (BE_Zentus keys, etc.): ignore unknown keys
        # instead of refusing to start.
        extra = "ignore"

    @classmethod
    def settings_customise_sources(cls, settings_cls, init_settings, env_settings, dotenv_settings,
                                   file_secret_settings):
        # .env beats OS environment variables: a stale machine-wide GEMINI_API_KEY / GROQ_API_KEY
        # (set for another project) must not silently override the key written in this app's .env.
        # Keys absent from .env still come from the environment (deploys without a .env file).
        return init_settings, dotenv_settings, env_settings, file_secret_settings


import os as _os

# EDUGUARD_ENV_FILE="" disables .env (tests); default reads ./.env
settings = Settings(_env_file=_os.getenv("EDUGUARD_ENV_FILE", ".env") or None)
