"""
Pydantic models for request/response validation in chatbot service.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ChatRequest(BaseModel):
    """Request to send a chat message."""
    conversation_id: Optional[str] = Field(
        None,
        description="Conversation ID. If not provided, a new conversation is created."
    )
    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="User message text"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "abc123-def456",
                "message": "What is the capital of France?"
            }
        }


class ChatResponse(BaseModel):
    """Response containing assistant's reply."""
    conversation_id: str = Field(..., description="Conversation ID")
    message: str = Field(..., description="Assistant's response")
    created_at: str = Field(..., description="ISO 8601 timestamp")
    model: str = Field(..., description="LLM model used")

    class Config:
        json_schema_extra = {
            "example": {
                "conversation_id": "abc123-def456",
                "message": "The capital of France is Paris.",
                "created_at": "2026-05-22T10:30:01.234Z",
                "model": "llama-3.1-70b-versatile"
            }
        }


class MessageItem(BaseModel):
    """Individual message in conversation history."""
    id: str
    role: str = Field(..., pattern=r'^(user|assistant|system)$')
    content: str
    created_at: str
    token_count: int


class ConversationResponse(BaseModel):
    """Conversation metadata response."""
    id: str
    created_at: str
    updated_at: str
    message_count: int
    model_name: str

    class Config:
        json_schema_extra = {
            "example": {
                "id": "abc123-def456",
                "created_at": "2026-05-22T10:00:00.000Z",
                "updated_at": "2026-05-22T10:30:00.000Z",
                "message_count": 4,
                "model_name": "llama-3.1-70b-versatile"
            }
        }


class ConversationHistoryResponse(BaseModel):
    """Full conversation history with messages."""
    conversation: ConversationResponse
    messages: List[MessageItem]


class ErrorResponse(BaseModel):
    """Generic error response."""
    error: str
    detail: Optional[str] = None
