# backend/models/upload.py

from pydantic import BaseModel, ConfigDict
from typing import Optional, List

class ProcessingResponse(BaseModel):
    """Response model for file processing."""
    processing_id: str
    status: str
    message: str
    timestamp: str
    file_name: Optional[str] = None
    form_type: Optional[str] = None
    page_count: Optional[int] = None
    total_pages: Optional[int] = None
    processing_ids: Optional[List[str]] = None
    errors: Optional[List[dict]] = None

    model_config = ConfigDict(
        populate_by_name=True,
        by_alias=True,  # ✅ Serialize using aliases
    )


class ErrorResponse(BaseModel):
    """Error response model."""
    error: str
    detail: str
    timestamp: str