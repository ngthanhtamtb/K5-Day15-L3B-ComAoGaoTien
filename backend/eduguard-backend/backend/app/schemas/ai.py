from pydantic import BaseModel
from typing import Optional, List, Dict, Any

class AIGenerateOutlineRequest(BaseModel):
    topic: str
    target_audience: Optional[str] = None
    presentation_length: Optional[int] = 10
    tone: Optional[str] = "professional"

class AIGenerateSlideContentRequest(BaseModel):
    slide_title: str
    slide_context: Optional[str] = None
    content_type: str = "bullet_points"

class AIImproveContentRequest(BaseModel):
    content: str
    improvement_type: str = "clarity"

class AIGenerateImageRequest(BaseModel):
    prompt: str
    style: Optional[str] = "professional"
    aspect_ratio: Optional[str] = "16:9"

class AIDocumentProcessRequest(BaseModel):
    document_url: str
    processing_type: str = "extract_outline"

class AIGenerationResponse(BaseModel):
    job_id: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class AIJobStatus(BaseModel):
    job_id: str
    status: str
    progress: Optional[int] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
