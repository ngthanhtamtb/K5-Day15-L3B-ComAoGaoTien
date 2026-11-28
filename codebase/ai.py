"""Nối model — chỗ DUY NHẤT trong bản chạy thử gọi model AI. NHÓM VIẾT phần gọi model thật.

Hợp đồng (giữ nguyên để khung đo được token):
    call_model(system: str, user: str) -> dict với 4 khoá
        "text":       str   chữ model trả về
        "model":      str   tên model đã gọi (để tra giá ở bảng giá model)
        "tokens_in":  int   số token vào, lấy từ trường usage trong phản hồi API — KHÔNG ước lượng
        "tokens_out": int   số token ra, gồm cả token suy luận / suy nghĩ nếu API tính riêng
    @model_call (từ tracing.py) tự ghi mỗi lần gọi vào trace; agent.py gọi call_model bao nhiêu lần
    cũng được, khung tự cộng token.
    Lỗi gọi model (hết lượt, sai key, mất mạng): cứ để exception bay ra — khung ghi lỗi vào cột error.

Chế độ giả (mặc định khi .env chưa có MODEL_PROVIDER, hoặc MODEL_PROVIDER=fake):
    trả một câu giả cố định, model "fake", token 0 — để luồng chạy hết từ trước CP2 (guide bước 3.2).
    Lượt `run.py eval` / `run.py simulate` chạy bằng model giả KHÔNG được tính.

Nối model thật: điền .env (chép từ .env.example), rồi viết nhánh gọi API ở dưới theo docs/connect-model.md
(có ví dụ OpenAI, Claude, model chạy trên máy, và cách nối nhà cung cấp khác). Không dán API key vào file này.
"""
import http.client
import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request

from tracing import model_call

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_env(path=os.path.join(ROOT, ".env")):
    """Đọc file .env (KEY=VALUE mỗi dòng) vào biến môi trường, không ghi đè biến đã có. Khung — không cần sửa."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env()
MODEL_PROVIDER = (os.environ.get("MODEL_PROVIDER") or "fake").strip().lower()
MODEL_NAME = (os.environ.get("MODEL_NAME") or "").strip()
API_KEY = (os.environ.get("API_KEY") or "").strip()


API_BASE_URL = (os.environ.get("API_BASE_URL") or "https://api.anthropic.com").strip().rstrip("/")
SHOW_RAW = False   # True: in nguyên phản hồi API khi cần tìm tên trường
MAX_TOKENS = 8192
RETRIES = 4


def _post_via_curl(url, req_headers, data_bytes, timeout):
    """Fallback bằng curl.exe khi urllib bị ngắt TLS/WinError 10054 bởi proxy."""
    curl = shutil.which("curl.exe") or shutil.which("curl")
    if not curl:
        return None
    cmd = [curl, "-sS", "-X", "POST", url, "--data-binary", "@-", "-w", "\n%{http_code}", "--max-time", str(timeout)]
    for k, v in req_headers.items():
        cmd.extend(["-H", "%s: %s" % (k, v)])
    proc = subprocess.run(cmd, input=data_bytes, capture_output=True, timeout=timeout + 5)
    if proc.returncode != 0:
        raise RuntimeError("curl lỗi (%d): %s" % (proc.returncode, proc.stderr.decode("utf-8", "replace")[:200]))
    out = proc.stdout.decode("utf-8", "replace")
    body_text, _, code_str = out.rpartition("\n")
    code = int(code_str.strip()) if code_str.strip().isdigit() else 0
    return code, body_text


def post_json(url, headers, body, timeout=120):
    """POST JSON, trả JSON phản hồi. Dùng urllib, fallback sang curl.exe nếu bị WinError 10054."""
    data_bytes = json.dumps(body).encode("utf-8")
    req_headers = dict({
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Connection": "close",
    }, **headers)
    last = None
    for attempt in range(RETRIES):
        req = urllib.request.Request(url, data=data_bytes, method="POST", headers=req_headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = json.loads(r.read().decode("utf-8"))
            if SHOW_RAW:
                print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
            return data
        except urllib.error.HTTPError as e:
            body_text = e.read().decode("utf-8", "replace")
            last = RuntimeError("HTTP %d: %s" % (e.code, body_text[:300]))
            rate_limited = e.code == 403 and "rate_limit" in body_text
            if e.code not in (429, 500, 502, 503, 529) and not rate_limited:
                raise last
            if rate_limited:
                m = re.search(r"in\s+(\d+(?:\.\d+)?)\s+second", body_text)
                time.sleep(min(float(m.group(1)) + 1 if m else 5, 30))
                continue
        except (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException, OSError) as e:
            last = RuntimeError("lỗi mạng: %s" % e)
            # Khi urllib bị WinError 10054 / ngắt TLS, thử fallback qua curl.exe (dùng Schannel của Windows)
            try:
                res = _post_via_curl(url, req_headers, data_bytes, timeout)
                if res is not None:
                    code, body_text = res
                    if 200 <= code < 300:
                        data = json.loads(body_text)
                        if SHOW_RAW:
                            print(json.dumps(data, ensure_ascii=False, indent=2)[:3000])
                        return data
                    last = RuntimeError("HTTP %d: %s" % (code, body_text[:300]))
                    rate_limited = code == 403 and "rate_limit" in body_text
                    if code not in (429, 500, 502, 503, 529) and not rate_limited:
                        raise last
                    if rate_limited:
                        m = re.search(r"in\s+(\d+(?:\.\d+)?)\s+second", body_text)
                        time.sleep(min(float(m.group(1)) + 1 if m else 5, 30))
                        continue
            except RuntimeError as ce:
                if "HTTP " in str(ce):
                    raise
                last = ce
        time.sleep(2 * (attempt + 1))
    raise last


def call_claude(system, user, model):
    """Model có token suy nghĩ tính vào max_tokens: nếu bị cắt (max_tokens) mà chưa có chữ trả lời thì gọi lại với
    ngân sách gấp đôi (tối đa 3 lần). Token của MỌI lần gọi đều được cộng, vì đều tốn tiền."""
    budget, tin, tout = MAX_TOKENS, 0, 0
    for _ in range(3):
        data = post_json(API_BASE_URL + "/v1/messages",
                         {"x-api-key": API_KEY, "anthropic-version": "2023-06-01"},
                         {"model": model, "max_tokens": budget, "system": system or "",
                          "messages": [{"role": "user", "content": user}]})
        text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        u = data["usage"]
        tin += u["input_tokens"]
        tout += u["output_tokens"]
        if text.strip() or data.get("stop_reason") != "max_tokens":
            break
        budget *= 2
    return {"text": text, "tokens_in": tin, "tokens_out": tout}


@model_call
def call_model(system: str, user: str, model: str = None) -> dict:
    """model=None dùng MODEL_NAME trong .env. Luồng hai model: truyền tên model cho từng lần gọi."""
    if MODEL_PROVIDER == "fake":
        last = (user.strip().splitlines() or [""])[-1]
        return {"text": "[câu trả lời giả — chưa nối model] " + last[:60], "model": "fake", "tokens_in": 0, "tokens_out": 0}
    name = model or MODEL_NAME
    if MODEL_PROVIDER == "anthropic":
        r = call_claude(system, user, name)
    else:
        raise NotImplementedError("MODEL_PROVIDER=%s chưa được hỗ trợ trong codebase/ai.py" % MODEL_PROVIDER)
    return {"text": r["text"], "model": name,
            "tokens_in": int(r["tokens_in"]), "tokens_out": int(r["tokens_out"])}
