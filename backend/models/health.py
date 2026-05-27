from pydantic import BaseModel, Field
from typing import Optional

# ==================== RESPONSE MODELS ====================
class ServiceStatus(BaseModel):
    """Individual service status."""
    status: str = Field(..., description="Service status (healthy, unhealthy)")
    latency_ms: Optional[float] = Field(None, description="Response time in milliseconds")
    version: Optional[str] = Field(None, description="Service version")
    error: Optional[str] = Field(None, description="Error message if unhealthy")
    details: Optional[dict] = Field(None, description="Additional diagnostic details")


class HealthCheckResponse(BaseModel):
    """Overall health check response."""
    status: str = Field(..., description="Overall status (healthy, degraded, unhealthy)")
    timestamp: str = Field(..., description="Check timestamp (ISO 8601)")
    duration_ms: Optional[float] = Field(None, description="Check duration in milliseconds")
    services: dict[str, ServiceStatus] = Field(..., description="Individual service statuses")
    version: str = Field(..., description="API version")
    environment: str = Field(..., description="Environment name")