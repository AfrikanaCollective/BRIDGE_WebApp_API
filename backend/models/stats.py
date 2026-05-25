# backend/models/stats.py

from typing import Dict
from pydantic import BaseModel, Field

# ==================== RESPONSE MODELS ====================
class ProcessingTimeStats(BaseModel):
    """Processing time statistics."""
    average: float = Field(..., description="Average processing time in ms")
    max: int = Field(..., description="Maximum processing time in ms")
    min: int = Field(..., description="Minimum processing time in ms")


class StatsOverview(BaseModel):
    """Aggregate statistics overview."""
    period_days: int = Field(..., description="Number of days in the period")
    date_range: Dict[str, str] = Field(..., description="Start and end dates")
    total_processed: int = Field(..., description="Total forms processed")
    by_status: Dict[str, int] = Field(..., description="Count by status")
    by_form_type: Dict[str, int] = Field(..., description="Count by form type")
    processing_time_ms: ProcessingTimeStats = Field(..., description="Processing time stats")
    success_rate: float = Field(..., description="Percentage of successful completions")


# ==================== EXTENDED RESPONSE MODELS ====================
class ProcessingTimeBreakdown(BaseModel):
    """Processing time breakdown by component."""
    llm_seconds: ProcessingTimeStats = Field(
        ...,
        description="LLM-only processing time (text generation only)"
    )
    agent_seconds: ProcessingTimeStats = Field(
        ...,
        description="Agent processing time (extraction + processing)"
    )
    total_seconds: ProcessingTimeStats = Field(
        ...,
        description="Combined LLM + Agent processing time"
    )


class StatsOverviewExtended(StatsOverview):
    """Extended statistics with breakdown of processing times."""
    processing_time_breakdown: ProcessingTimeBreakdown = Field(
        ...,
        description="Breakdown of processing times by component"
    )
