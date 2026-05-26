# backend/models/history.py

"""
Data models for history and form records.
Supports both snake_case (internal) and camelCase (API) field names.
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, Dict, Any
from datetime import datetime


class FormRecord(BaseModel):
    """
    Represents a single processed form record.
    Uses camelCase for API responses while supporting snake_case internally.
    """

    id: str = Field(
        ...,
        alias="_id",
        description="MongoDB document ID",
        serialization_alias="id"
    )

    # Metadata fields with camelCase aliases
    timestamp: Optional[datetime] = Field(
        default=None,
        description="When the form was processed",
        serialization_alias="timestamp"
    )

    imageFilename: Optional[str] = Field(
        default=None,
        alias="image_filename",
        description="Original filename of the image",
        serialization_alias="imageFilename"
    )

    formType: Optional[str] = Field(
        default=None,
        alias="form_type",
        description="Type of form (ITF, NAR, DSC, DAI, DOC)",
        serialization_alias="formType"
    )

    caseId: Optional[str] = Field(
        default=None,
        alias="case_id",
        description="Case or patient identifier",
        serialization_alias="caseId"
    )

    pageNumber: Optional[int] = Field(
        default=None,
        alias="page_number",
        description="Page number if multi-page form",
        serialization_alias="pageNumber"
    )

    fileSizeMb: Optional[float] = Field(
        default=None,
        alias="file_size_mb",
        description="Size of the uploaded file in MB",
        serialization_alias="fileSizeMb"
    )

    # Processing metadata
    status: Optional[str] = Field(
        default=None,
        description="Processing status (success, error, pending)",
        serialization_alias="status"
    )

    model: Optional[str] = Field(
        default=None,
        description="LLM model used for processing",
        serialization_alias="model"
    )

    agentProcessed: bool = Field(
        default=False,
        alias="agent_processed",
        description="Whether agent-based extraction was performed",
        serialization_alias="agentProcessed"
    )

    # Processing times
    processingTimeLlmSeconds: Optional[float] = Field(
        default=None,
        alias="processing_time_llm_seconds",
        description="Time spent in LLM processing (seconds)",
        serialization_alias="processingTimeLlmSeconds"
    )

    processingTimeAgentSeconds: Optional[float] = Field(
        default=None,
        alias="processing_time_agent_seconds",
        description="Time spent in agent processing (seconds)",
        serialization_alias="processingTimeAgentSeconds"
    )

    # Content fields
    rawJson: Optional[str] = Field(
        default=None,
        alias="raw_json",
        description="Raw JSON response from LLM",
        serialization_alias="rawJsonPreview"
    )

    cleanedJson: Optional[Dict[str, Any]] = Field(
        default=None,
        alias="cleaned_json",
        description="Cleaned and structured JSON data",
        serialization_alias="cleanedJson"
    )

    caseSummary: Optional[str] = Field(
        default=None,
        alias="case_summary",
        description="Summary of extracted case information",
        serialization_alias="caseSummary"
    )

    # Metrics
    metrics: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Processing metrics from LLM/agent",
        serialization_alias="metrics"
    )

    # Additional optional fields
    coverage: Optional[float] = Field(
        default=None,
        description="Coverage of extracted required fields",
        serialization_alias="coverage"
    )

    completeness: Optional[float] = Field(
        default=None,
        description="Completeness score of extraction",
        serialization_alias="completeness"
    )

    processingId: Optional[str] = Field(
        default=None,
        alias="processing_id",
        description="Processing identifier",
        serialization_alias="processingId"
    )

    createdAt: Optional[datetime] = Field(
        default=None,
        alias="created_at",
        description="Record creation timestamp",
        serialization_alias="createdAt"
    )

    updatedAt: Optional[datetime] = Field(
        default=None,
        alias="updated_at",
        description="Record update timestamp",
        serialization_alias="updatedAt"
    )

    fileUrl: Optional[str] = Field(
        default=None,
        alias="file_url",
        description="Associated file URL",
        serialization_alias="fileUrl"
    )

    errorMessage: Optional[str] = Field(
        default=None,
        alias="error_message",
        description="Error message if processing failed",
        serialization_alias="errorMessage"
    )

    extractedData: Optional[Dict[str, Any]] = Field(
        default=None,
        alias="extracted_data",
        description="Raw extracted data",
        serialization_alias="extractedData"
    )

    # Validators
    @field_validator('timestamp', 'createdAt', 'updatedAt', mode='before')
    @classmethod
    def parse_timestamp(cls, v):
        """Convert string timestamps to datetime objects."""
        if v is None or v == "":
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            if not v or v.strip() == "":
                return None
            try:
                # Try ISO format with timezone (like '2026-05-25T05:46:02.671741+00:00')
                return datetime.fromisoformat(v.replace('Z', '+00:00'))
            except (ValueError, AttributeError):
                try:
                    # Try ISO format without timezone
                    return datetime.fromisoformat(v)
                except (ValueError, AttributeError):
                    return None
        return v

    model_config = ConfigDict(
        populate_by_name=True,  # Allow both 'id' and aliased '_id'
        from_attributes=True,
        extra='allow',  # Allow extra fields from MongoDB documents
        by_alias=True,  # ✅ Serialize using aliases (camelCase)
    )


class HistoryResponse(BaseModel):
    """Response model for history API endpoint."""
    totalCount: int = Field(
        ...,
        alias="total_count",
        description="Total number of records",
        serialization_alias="totalCount"
    )

    page: int = Field(
        ...,
        description="Current page number",
        serialization_alias="page"
    )

    pageSize: int = Field(
        ...,
        alias="page_size",
        description="Records per page",
        serialization_alias="pageSize"
    )

    totalPages: int = Field(
        ...,
        alias="total_pages",
        description="Total number of pages",
        serialization_alias="totalPages"
    )

    records: list[FormRecord] = Field(
        ...,
        description="List of form records",
        serialization_alias="records"
    )

    model_config = ConfigDict(
        populate_by_name=True,
        by_alias=True,  # ✅ Serialize using aliases
    )


class HistoryStats(BaseModel):
    """Statistics about processing history."""
    totalProcessed: int = Field(
        ...,
        alias="total_processed",
        description="Total forms processed",
        serialization_alias="totalProcessed"
    )

    byStatus: Dict[str, int] = Field(
        ...,
        alias="by_status",
        description="Count by processing status",
        serialization_alias="byStatus"
    )

    byFormType: Dict[str, int] = Field(
        ...,
        alias="by_form_type",
        description="Count by form type",
        serialization_alias="byFormType"
    )

    successRate: float = Field(
        ...,
        alias="success_rate",
        description="Percentage of successful processing",
        serialization_alias="successRate"
    )

    model_config = ConfigDict(
        populate_by_name=True,
        by_alias=True,  # ✅ Serialize using aliases
    )


class RecordResponse(BaseModel):
    """Single record response."""
    record: FormRecord = Field(
        ...,
        description="Form record details",
        serialization_alias="record"
    )

    fileUrl: Optional[str] = Field(
        None,
        alias="file_url",
        description="Associated file URL",
        serialization_alias="fileUrl"
    )

    model_config = ConfigDict(
        populate_by_name=True,
        by_alias=True,  # ✅ Serialize using aliases
    )


class DeleteResponse(BaseModel):
    """Deletion confirmation response."""
    deleted: bool = Field(
        ...,
        description="Deletion success status",
        serialization_alias="deleted"
    )

    processingId: str = Field(
        ...,
        alias="processing_id",
        description="Deleted processing identifier",
        serialization_alias="processingId"
    )

    message: str = Field(
        ...,
        description="Deletion details",
        serialization_alias="message"
    )

    model_config = ConfigDict(
        populate_by_name=True,
        by_alias=True,  # ✅ Serialize using aliases
    )
