# backend/models/form.py

from datetime import datetime, UTC
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


class FormResponse(BaseModel):
    id: Optional[str] = Field(None, alias="_id")
    filename: str
    file_size: int
    file_path: str
    user_ip: str

    # Processing
    qwen_response: str
    processing_time: float

    # Metadata
    extracted_data: Dict[str, Any]
    confidence_score: float

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now(UTC).isoformat())
    updated_at: datetime = Field(default_factory=datetime.now(UTC).isoformat())

    # Cache
    cached: bool = False
    cache_key: Optional[str] = None

    class Config:
        populate_by_name = True


class UploadRequest(BaseModel):
    filename: str
    content_type: str


class UploadResponse(BaseModel):
    success: bool
    message: str
    response_id: str
    response: str
    processing_time: float
    extracted_data: Dict[str, Any]
