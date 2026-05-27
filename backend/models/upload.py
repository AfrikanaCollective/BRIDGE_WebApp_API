# backend/models/upload.py

from pydantic import BaseModel
from typing import Optional

class ProcessingResponse(BaseModel):
    """Response model for file processing."""
    processing_id: str
    status: str
    message: str
    timestamp: str
    file_name: Optional[str] = None
    form_type: Optional[str] = None


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: str
    timestamp: str