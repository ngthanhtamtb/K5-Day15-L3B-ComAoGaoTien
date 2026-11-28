"""File-based storage for the edu module.

Everything lives under settings.EDU_DATA_DIR (default data/edu). main.py already mounts
`data/` at `/static`, so a file at data/edu/x/y.png is served at /static/edu/x/y.png
without any new route.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from typing import Any, Optional

from app.core.config import settings

_SAFE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def edu_root() -> str:
    root = os.path.abspath(settings.EDU_DATA_DIR)
    os.makedirs(root, exist_ok=True)
    return root


def path(*parts: str) -> str:
    p = os.path.join(edu_root(), *parts)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    return p


def url_for(*parts: str) -> str:
    """Public URL of a file under EDU_DATA_DIR. main.py mounts EDU_DATA_DIR at /static/edu,
    so this works wherever EDU_DATA_DIR lives (not only inside data/)."""
    rel = "/".join(p.strip("/\\").replace(os.sep, "/") for p in parts if p)
    return f"{settings.EDU_PUBLIC_BASE_URL.rstrip('/')}/static/edu/{rel}"


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def check_id(value: str) -> str:
    if not _SAFE_ID.match(value or ""):
        raise ValueError("invalid id")
    return value


def save_json(obj: Any, *parts: str) -> None:
    p = path(*parts)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, p)


def load_json(*parts: str) -> Optional[Any]:
    p = os.path.join(edu_root(), *parts)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as fh:
        return json.load(fh)
