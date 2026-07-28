# backend/models/stats.py

from typing import Dict
from pydantic import BaseModel, Field

# ==================== RESPONSE MODELS ====================
class ProcessingTimeStats(BaseModel):
    """Processing time statistics."""
    average: float = Field(
        ...,
        description="Average processing time in seconds",
        serialization_alias="average"
    )
    max: float = Field(
        ...,
        description="Maximum processing time in seconds",
        serialization_alias="max"
    )
    min: float = Field(
        ...,
        description="Minimum processing time in seconds",
        serialization_alias="min"
    )

    class Config:
        populate_by_name = True


class StatsOverview(BaseModel):
    """Aggregate statistics overview."""
    period_days: int = Field(
        ...,
        description="Number of days in the period",
        serialization_alias="period_days"
    )
    date_range: Dict[str, str] = Field(
        ...,
        description="Start and end dates",
        serialization_alias="date_range"
    )
    total_processed: int = Field(
        ...,
        description="Total forms processed",
        serialization_alias="total_processed"
    )
    by_status: Dict[str, int] = Field(
        ...,
        description="Count by status",
        serialization_alias="by_status"
    )
    by_form_type: Dict[str, int] = Field(
        ...,
        description="Count by form type",
        serialization_alias="by_form_type"
    )
    success_rate: float = Field(
        ...,
        description="Percentage of successful completions (0-100)",
        serialization_alias="success_rate"
    )
    active_sessions: float = Field(
        ...,
        description="Number of active sessions",
        serialization_alias="active_sessions"
    )

    class Config:
        populate_by_name = True


# ==================== EXTENDED RESPONSE MODELS ====================
class ProcessingTimeBreakdown(BaseModel):
    """Processing time breakdown by component."""
    llm_seconds: ProcessingTimeStats = Field(
        ...,
        description="LLM-only processing time (text generation only)",
        serialization_alias="llm_seconds"
    )
    agent_seconds: ProcessingTimeStats = Field(
        ...,
        description="Agent processing time (extraction + processing)",
        serialization_alias="agent_seconds"
    )
    total_seconds: ProcessingTimeStats = Field(
        ...,
        description="Combined LLM + Agent processing time",
        serialization_alias="total_seconds"
    )

    class Config:
        populate_by_name = True


class StatsOverviewExtended(StatsOverview):
    """Extended statistics with breakdown of processing times."""
    processing_time_breakdown: ProcessingTimeBreakdown = Field(
        ...,
        description="Breakdown of processing times by component",
        serialization_alias="processing_time_breakdown"
    )

    class Config:
        populate_by_name = True
