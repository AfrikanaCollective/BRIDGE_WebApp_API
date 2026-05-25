# backend/models/history.py

"""
Data models for history and form records.
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, Dict, Any
from datetime import datetime


class FormRecord(BaseModel):
    """
    Represents a single processed form record.

    Fields can be optional to handle incomplete or partially processed records.
    """
    id: str = Field(..., alias="_id", description="MongoDB document ID")

    # Make timestamp Optional and add validator to parse strings
    timestamp: Optional[datetime] = Field(
        default=None,
        description="When the form was processed"
    )

    # Make image_filename Optional (may not exist in older records)
    image_filename: Optional[str] = Field(
        default=None,
        description="Original filename of the image"
    )

    # Make form_type Optional (may not exist in older records)
    form_type: Optional[str] = Field(
        default=None,
        description="Type of form (ITF, NAR, DSC, DAI, DOC)"
    )

    case_id: Optional[str] = Field(
        default=None,
        description="Case or patient identifier (optional, may be null)"
    )

    page_number: Optional[int] = Field(
        default=None,
        description="Page number if multi-page form"
    )

    file_size_mb: Optional[float] = Field(
        default=None,
        description="Size of the uploaded file in MB"
    )

    # Processing metadata
    # ✅ FIXED: Make status Optional with default
    status: Optional[str] = Field(
        default=None,
        description="Processing status (success, error, pending)"
    )

    model: Optional[str] = Field(
        default=None,
        description="LLM model used for processing"
    )

    agent_processed: bool = Field(
        default=False,
        description="Whether agent-based extraction was performed"
    )

    # Processing times
    processing_time_llm_seconds: Optional[float] = Field(
        default=None,
        description="Time spent in LLM processing (seconds)"
    )

    processing_time_agent_seconds: Optional[float] = Field(
        default=None,
        description="Time spent in agent processing (seconds)"
    )

    # Content fields
    response_preview: Optional[str] = Field(
        default=None,
        description="Preview of extracted data (text format)"
    )

    raw_json_preview: Optional[str] = Field(
        default=None,
        description="Raw JSON response from LLM"
    )

    cleaned_json: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Cleaned and structured JSON data"
    )

    case_summary: Optional[str] = Field(
        default=None,
        description="Summary of extracted case information"
    )

    # Metrics
    metrics: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Processing metrics from LLM/agent"
    )

    # Add validator to parse string timestamps to datetime
    @field_validator('timestamp', mode='before')
    @classmethod
    def parse_timestamp(cls, v):
        """Convert string timestamps to datetime objects."""
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            try:
                # Try ISO format with timezone (like '2026-05-25T05:46:02.671741+00:00')
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                try:
                    # Try ISO format without timezone
                    return datetime.fromisoformat(v)
                except (ValueError, AttributeError):
                    # If parsing fails, log and return None
                    return None
        return v

    # Use ConfigDict for Pydantic v2
    model_config = ConfigDict(
        populate_by_name=True,  # Allow both 'id' and aliased '_id'
        from_attributes=True,
        extra='allow',  # Allow extra fields from MongoDB documents
    )


class HistoryResponse(BaseModel):
    """Response model for history API endpoint."""
    total_count: int = Field(..., description="Total number of records")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Records per page")
    total_pages: int = Field(..., description="Total number of pages")
    records: list[FormRecord] = Field(..., description="List of form records")

    model_config = ConfigDict(populate_by_name=True)


class HistoryStats(BaseModel):
    """Statistics about processing history."""
    total_processed: int = Field(..., description="Total forms processed")
    by_status: Dict[str, int] = Field(..., description="Count by processing status")
    by_form_type: Dict[str, int] = Field(..., description="Count by form type")
    success_rate: float = Field(..., description="Percentage of successful processing")

    model_config = ConfigDict(populate_by_name=True)


class RecordResponse(BaseModel):
    """Single record response."""
    record: FormRecord = Field(..., description="Form record details")
    file_url: Optional[str] = Field(None, description="Associated file URL")

    model_config = ConfigDict(populate_by_name=True)


class DeleteResponse(BaseModel):
    """Deletion confirmation response."""
    deleted: bool = Field(..., description="Deletion success status")
    processing_id: str = Field(..., description="Deleted processing identifier")
    message: str = Field(..., description="Deletion details")

    model_config = ConfigDict(populate_by_name=True)
