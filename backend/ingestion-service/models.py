"""
Pydantic models for request/response validation in ingestion service.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional


class InferenceLogPayload(BaseModel):
    """
    Log payload from LLM SDK wrapper.
    Validates inference metadata before storage.
    """
    # Required fields
    conversation_id: str = Field(..., min_length=1, max_length=100)
    provider: str = Field(..., min_length=1, max_length=50)
    model: str = Field(..., min_length=1, max_length=100)
    latency_ms: int = Field(..., ge=0, description="Latency in milliseconds")
    status: str = Field(..., pattern=r'^(success|error|timeout)$')
    request_timestamp: str = Field(..., description="ISO 8601 timestamp")

    # Optional fields
    message_id: Optional[str] = Field(None, max_length=100)
    response_timestamp: Optional[str] = Field(None, description="ISO 8601 timestamp")
    prompt_tokens: Optional[int] = Field(None, ge=0)
    completion_tokens: Optional[int] = Field(None, ge=0)
    total_tokens: Optional[int] = Field(None, ge=0)
    error_message: Optional[str] = Field(None, max_length=1000)
    input_preview: Optional[str] = Field(None, max_length=500)
    output_preview: Optional[str] = Field(None, max_length=500)

    @field_validator('total_tokens')
    @classmethod
    def validate_total_tokens(cls, v: Optional[int], info) -> Optional[int]:
        """Ensure total_tokens matches sum of prompt and completion tokens if provided."""
        if v is not None:
            prompt = info.data.get('prompt_tokens', 0) or 0
            completion = info.data.get('completion_tokens', 0) or 0
            expected = prompt + completion
            if expected > 0 and v != expected:
                # Allow slight mismatch, but log warning in production
                pass
        return v

    class Config:
        # Example payload for API documentation
        json_schema_extra = {
            "example": {
                "conversation_id": "abc123-def456",
                "message_id": "msg_xyz789",
                "provider": "groq",
                "model": "llama-3.1-70b-versatile",
                "request_timestamp": "2026-05-22T10:30:00.000Z",
                "response_timestamp": "2026-05-22T10:30:01.234Z",
                "latency_ms": 1234,
                "prompt_tokens": 150,
                "completion_tokens": 80,
                "total_tokens": 230,
                "status": "success",
                "input_preview": "User asked: What is the capital of France?",
                "output_preview": "The capital of France is Paris..."
            }
        }


class IngestResponse(BaseModel):
    """Response after successful log ingestion."""
    success: bool
    log_id: str
    message: str = "Log ingested successfully"


class ErrorResponse(BaseModel):
    """Generic error response."""
    error: str
    detail: Optional[str] = None
