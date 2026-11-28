import json
import base64
import gzip
import uuid
import os
from typing import List, Dict, Any,Optional

from fastapi import UploadFile, Request, HTTPException
from bs4 import BeautifulSoup
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad

from app.core.config import settings

# Load FERNET_KEY from environment variable
# settings reads .env (pydantic-settings); os.getenv alone missed keys that live only in .env
FERNET_KEY = os.getenv("FERNET_KEY", "") or settings.FERNET_KEY
if not FERNET_KEY:
    raise ValueError("FERNET_KEY must be set in environment variables")
SECRET_KEY = base64.b64decode(FERNET_KEY)  # 32 bytes


def encode_response_data(data: dict) -> str:
    json_str = json.dumps(data, ensure_ascii=False)
    compressed = gzip.compress(json_str.encode("utf-8"))

    cipher = AES.new(SECRET_KEY, AES.MODE_ECB)
    encrypted = cipher.encrypt(pad(compressed, AES.block_size))

    return base64.b64encode(encrypted).decode("utf-8")


def encode_no_key_response_data(data):
    json_str = json.dumps(data, ensure_ascii=False)
    compressed = gzip.compress(json_str.encode("utf-8"))
    return base64.b64encode(compressed).decode("utf-8")


def improve_text_element(text_to_improve: str, improve_func) -> str:
    try:
        soup = BeautifulSoup(text_to_improve, "html.parser")
        if soup.find():
            original_text = soup.get_text(strip=True)
            improved_text = improve_func(original_text)
            for elem in soup.find_all():
                if elem.string and elem.string.strip() == original_text:
                    elem.string.replace_with(improved_text)
                    break
            return str(soup)
        else:
            return improve_func(text_to_improve)
    except Exception as e:
        return improve_func(text_to_improve)


def extract_text_and_prepare_prompt(raw_html_or_text: str) -> tuple[str, str, bool]:
    soup = BeautifulSoup(raw_html_or_text, "html.parser")
    is_html = bool(soup.find())
    extracted_text = soup.get_text(strip=True) if is_html else raw_html_or_text
    return extracted_text, raw_html_or_text, is_html

def inject_text_back_into_html(html: str, new_text: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    original_text = soup.get_text(strip=True)

    for elem in soup.find_all():
        if elem.string and elem.string.strip() == original_text:
            elem.string.replace_with(new_text)
            break
    return str(soup)


def parse_cover_url(request: Request, url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    if url.startswith(("http://", "https://", "s3://")):
        return url
    base_url = str(request.base_url).rstrip('/')
    return f"{base_url}/static{url}"


async def handle_thumbnail_upload(thumbnail_file: UploadFile) -> str:
    allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"]
    if thumbnail_file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}"
        )

    file_extension = thumbnail_file.filename.split(".")[-1] if "." in thumbnail_file.filename else "jpg"
    unique_filename = f"page_{uuid.uuid4()}.{file_extension}"

    upload_path = settings.UPLOAD_PAGE_DIR / unique_filename
    with open(upload_path, "wb") as buffer:
        content = await thumbnail_file.read()
        buffer.write(content)

    return f"/uploads/pages/{unique_filename}"


def _parse_enum_field(value: str, enum_class) -> Optional[Any]:
    if not value:
        return None
    try:
        return enum_class(value)
    except ValueError:
        return None


def _get_upload_path(url: str) -> str:
    return f"./uploads/{url.split('/uploads/')[-1]}"


# Target dimensions for templates (16:9 ratio)
TARGET_WIDTH = 1000.0
TARGET_HEIGHT = 562.5


def normalize_element_positions(
    elements: List[Dict[str, Any]],
    source_width: Optional[float] = None,
    source_height: Optional[float] = None,
    target_width: float = TARGET_WIDTH,
    target_height: float = TARGET_HEIGHT
) -> List[Dict[str, Any]]:
    """
    Normalize element positions from source dimensions to target dimensions.

    Args:
        elements: List of slide elements with left, top, width, height properties
        source_width: Original slide width (e.g., 1920, 1280, 960)
        source_height: Original slide height (e.g., 1080, 720, 540)
        target_width: Target width (default: 1000.0)
        target_height: Target height (default: 562.5)

    Returns:
        List of elements with normalized positions
    """
    if not elements:
        return elements

    # If source dimensions not provided, skip normalization
    if not source_width or not source_height:
        return elements

    # If source dimensions match target, no normalization needed
    if source_width == target_width and source_height == target_height:
        return elements

    # Calculate scale factors
    scale_x = target_width / source_width
    scale_y = target_height / source_height

    normalized_elements = []
    for element in elements:
        normalized_element = element.copy()

        # Normalize position and size properties
        if 'left' in normalized_element:
            normalized_element['left'] = normalized_element['left'] * scale_x
        if 'top' in normalized_element:
            normalized_element['top'] = normalized_element['top'] * scale_y
        if 'width' in normalized_element:
            normalized_element['width'] = normalized_element['width'] * scale_x
        if 'height' in normalized_element:
            normalized_element['height'] = normalized_element['height'] * scale_y

        normalized_elements.append(normalized_element)

    return normalized_elements


def normalize_slides_data(
    slides: List[Dict[str, Any]],
    source_width: Optional[float] = None,
    source_height: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Normalize all elements in a list of slides.

    Args:
        slides: List of slide data containing 'elements' field
        source_width: Original slide width
        source_height: Original slide height

    Returns:
        List of slides with normalized element positions
    """
    if not slides:
        return slides

    if not source_width or not source_height:
        return slides

    normalized_slides = []
    for slide in slides:
        normalized_slide = slide.copy()

        if 'elements' in normalized_slide:
            normalized_slide['elements'] = normalize_element_positions(
                normalized_slide['elements'],
                source_width,
                source_height
            )

        normalized_slides.append(normalized_slide)

    return normalized_slides
