"""
Chatbot Service - Multi-turn LLM chat with inference logging.
FastAPI application with CSRF protection and secure database handling.
"""
import secrets
import json
from datetime import datetime
from typing import Dict, List
from fastapi import FastAPI, HTTPException, Request, Path as FastAPIPath
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import func

from config import settings
from database import init_database, get_db, Conversation, Message
from llm_client import LoggingLLMClient
from models import ChatRequest, ChatResponse, ConversationResponse, ConversationHistoryResponse, MessageItem, ErrorResponse

# Create FastAPI app
app = FastAPI(
    title="LLM Chatbot Service",
    description="Multi-turn chatbot with inference logging",
    version="1.0.0"
)

# CORS middleware with explicit origin allowlist (security requirement)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token"],
)

# Initialize LLM client
llm_client = LoggingLLMClient()


@app.on_event("startup")
def startup_event():
    """Initialize database on startup."""
    init_database()
    print(f"Chatbot service started on {settings.host}:{settings.port}")
    print(f"Database: {settings.database_path}")
    print(f"CORS origins: {settings.allowed_origins_list}")


@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    """
    CSRF protection middleware.
    Generates CSRF token for GET requests, validates for POST/PUT/DELETE.
    """
    # For POST/PUT/DELETE, validate CSRF token
    if request.method in ["POST", "PUT", "DELETE"] and request.url.path != "/health":
        csrf_token_header = request.headers.get("X-CSRF-Token")
        csrf_token_cookie = request.cookies.get("csrf_token")

        if not csrf_token_header or not csrf_token_cookie:
            return JSONResponse(
                status_code=403,
                content={"error": "CSRF token missing"}
            )

        if csrf_token_header != csrf_token_cookie:
            return JSONResponse(
                status_code=403,
                content={"error": "CSRF token invalid"}
            )

    # Process request
    response = await call_next(request)

    # For GET requests, set CSRF token cookie if not present
    if request.method == "GET" and not request.cookies.get("csrf_token"):
        csrf_token = secrets.token_urlsafe(32)
        response.set_cookie(
            key="csrf_token",
            value=csrf_token,
            httponly=False,
            secure=settings.csrf_cookie_secure,
            samesite="lax",
            max_age=3600  # 1 hour
        )

    return response


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "chatbot",
        "timestamp": datetime.utcnow().isoformat(),
        "model": settings.default_model
    }


@app.post("/api/chat", response_model=ChatResponse, responses={
    400: {"model": ErrorResponse},
    500: {"model": ErrorResponse}
})
def chat(request: ChatRequest):
    """
    Send a message and get LLM response.
    Creates new conversation if conversation_id not provided.
    """
    try:
        with get_db() as db:
            # Get or create conversation
            if request.conversation_id:
                # Validate conversation ID format (alphanumeric, dashes, underscores only)
                if not request.conversation_id.replace('-', '').replace('_', '').isalnum():
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid conversation ID format"
                    )

                conversation = db.query(Conversation).filter(
                    Conversation.id == request.conversation_id
                ).first()

                if not conversation:
                    raise HTTPException(
                        status_code=404,
                        detail="Conversation not found"
                    )
            else:
                # Create new conversation
                conversation_id = secrets.token_urlsafe(16)
                conversation = Conversation(
                    id=conversation_id,
                    model_name=settings.default_model,
                    context_window_size=settings.context_window_size
                )
                db.add(conversation)
                db.commit()

            # Get recent messages for context (limit to context window size)
            recent_messages = db.query(Message).filter(
                Message.conversation_id == conversation.id
            ).order_by(
                Message.created_at.desc()
            ).limit(settings.context_window_size).all()

            # Reverse to chronological order
            recent_messages = list(reversed(recent_messages))

            # Build message list for LLM
            messages_for_llm = []
            for msg in recent_messages:
                messages_for_llm.append({
                    "role": msg.role,
                    "content": msg.content
                })

            # Add current user message
            user_message_id = secrets.token_urlsafe(16)
            user_message_content = request.message

            messages_for_llm.append({
                "role": "user",
                "content": user_message_content
            })

            # Store user message in database
            user_message = Message(
                id=user_message_id,
                conversation_id=conversation.id,
                role="user",
                content=user_message_content,
                token_count=llm_client.estimate_tokens(user_message_content)
            )
            db.add(user_message)
            db.commit()

            # Call LLM with logging
            assistant_response, metadata = llm_client.chat_completion(
                conversation_id=conversation.id,
                messages=messages_for_llm,
                message_id=None  # Will generate new ID for assistant message
            )

            # Store assistant message
            assistant_message_id = metadata.get("message_id", secrets.token_urlsafe(16))
            assistant_message = Message(
                id=assistant_message_id,
                conversation_id=conversation.id,
                role="assistant",
                content=assistant_response,
                token_count=metadata.get("completion_tokens", 0)
            )
            db.add(assistant_message)

            # Update conversation timestamp
            conversation.updated_at = datetime.utcnow().isoformat()
            db.commit()

            # Return response
            return ChatResponse(
                conversation_id=conversation.id,
                message=assistant_response,
                created_at=assistant_message.created_at,
                model=conversation.model_name
            )

    except HTTPException:
        raise
    except Exception as e:
        # Log error internally
        print(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


def _prepare_conversation(request: ChatRequest) -> Dict:
    """Create/resume a conversation, store user message, and build provider messages."""
    with get_db() as db:
        if request.conversation_id:
            if not request.conversation_id.replace('-', '').replace('_', '').isalnum():
                raise HTTPException(status_code=400, detail="Invalid conversation ID format")

            conversation = db.query(Conversation).filter(
                Conversation.id == request.conversation_id
            ).first()

            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")
        else:
            conversation_id = secrets.token_urlsafe(16)
            conversation = Conversation(
                id=conversation_id,
                model_name=settings.default_model,
                context_window_size=settings.context_window_size
            )
            db.add(conversation)
            db.commit()

        recent_messages = db.query(Message).filter(
            Message.conversation_id == conversation.id
        ).order_by(
            Message.created_at.desc()
        ).limit(settings.context_window_size).all()

        messages_for_llm = [
            {"role": msg.role, "content": msg.content}
            for msg in reversed(recent_messages)
        ]
        messages_for_llm.append({"role": "user", "content": request.message})

        user_message = Message(
            id=secrets.token_urlsafe(16),
            conversation_id=conversation.id,
            role="user",
            content=request.message,
            token_count=llm_client.estimate_tokens(request.message)
        )
        db.add(user_message)
        db.commit()

        return {
            "conversation_id": conversation.id,
            "messages_for_llm": messages_for_llm,
        }


def _store_assistant_message(conversation_id: str, content: str, metadata: Dict) -> str:
    """Persist streamed or complete assistant output."""
    with get_db() as db:
        assistant_message_id = metadata.get("message_id", secrets.token_urlsafe(16))
        assistant_message = Message(
            id=assistant_message_id,
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            token_count=metadata.get("completion_tokens", 0)
        )
        db.add(assistant_message)

        conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if conversation:
            conversation.updated_at = datetime.utcnow().isoformat()
            conversation.model_name = metadata.get("model", settings.default_model)

        db.commit()
        return assistant_message.created_at


def _sse(event: str, data: Dict | str) -> str:
    payload = data if isinstance(data, str) else json.dumps(data)
    return f"event: {event}\ndata: {payload}\n\n"


@app.post("/api/chat/stream", responses={
    400: {"model": ErrorResponse},
    500: {"model": ErrorResponse}
})
def stream_chat(request: ChatRequest):
    """Stream a response over Server-Sent Events and persist it when complete."""
    try:
        prepared = _prepare_conversation(request)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error preparing stream endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

    conversation_id = prepared["conversation_id"]
    messages_for_llm = prepared["messages_for_llm"]

    def event_stream():
        response_parts: list[str] = []
        metadata = None
        try:
            yield _sse("start", {"conversation_id": conversation_id, "model": settings.default_model})
            for chunk, maybe_metadata in llm_client.stream_chat_completion(
                conversation_id=conversation_id,
                messages=messages_for_llm,
                message_id=None
            ):
                if maybe_metadata is not None:
                    metadata = maybe_metadata
                    continue
                if chunk:
                    response_parts.append(chunk)
                    yield _sse("token", {"token": chunk})

            response_text = "".join(response_parts)
            if metadata is None:
                metadata = {"message_id": secrets.token_urlsafe(16), "completion_tokens": 0, "model": settings.default_model}
            created_at = _store_assistant_message(conversation_id, response_text, metadata)
            yield _sse("done", {
                "conversation_id": conversation_id,
                "message": response_text,
                "created_at": created_at,
                "model": metadata.get("model", settings.default_model),
            })
        except Exception as exc:
            print(f"Error in streaming chat endpoint: {str(exc)}")
            yield _sse("error", {"error": "Internal server error"})

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/api/conversations", response_model=List[ConversationResponse])
def list_conversations(limit: int = 50):
    """
    List recent conversations.
    Returns up to 50 most recent conversations by default.
    """
    try:
        with get_db() as db:
            # Get conversations with message counts
            conversations = db.query(
                Conversation,
                func.count(Message.id).label('message_count')
            ).outerjoin(
                Message, Message.conversation_id == Conversation.id
            ).group_by(
                Conversation.id
            ).order_by(
                Conversation.updated_at.desc()
            ).limit(min(limit, 100)).all()  # Cap at 100 for security

            # Format response
            result = []
            for conv, msg_count in conversations:
                result.append(ConversationResponse(
                    id=conv.id,
                    created_at=conv.created_at,
                    updated_at=conv.updated_at,
                    message_count=msg_count,
                    model_name=conv.model_name
                ))

            return result

    except Exception as e:
        print(f"Error listing conversations: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(
    conversation_id: str = FastAPIPath(..., pattern=r'^[a-zA-Z0-9_-]+$')
):
    """Delete a conversation and its messages."""
    try:
        with get_db() as db:
            conversation = db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()

            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")

            db.query(Message).filter(Message.conversation_id == conversation_id).delete()
            db.delete(conversation)
            db.commit()

            return {"success": True, "conversation_id": conversation_id}

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error deleting conversation: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get(
    "/api/conversations/{conversation_id}/messages",
    response_model=ConversationHistoryResponse
)
def get_conversation_history(
    conversation_id: str = FastAPIPath(..., pattern=r'^[a-zA-Z0-9_-]+$')
):
    """
    Get full conversation history with all messages.
    Path parameter validated to prevent path traversal attacks.
    """
    try:
        with get_db() as db:
            # Get conversation
            conversation = db.query(Conversation).filter(
                Conversation.id == conversation_id
            ).first()

            if not conversation:
                raise HTTPException(status_code=404, detail="Conversation not found")

            # Get all messages
            messages = db.query(Message).filter(
                Message.conversation_id == conversation_id
            ).order_by(
                Message.created_at.asc()
            ).all()

            # Count messages
            message_count = len(messages)

            # Format response
            return ConversationHistoryResponse(
                conversation=ConversationResponse(
                    id=conversation.id,
                    created_at=conversation.created_at,
                    updated_at=conversation.updated_at,
                    message_count=message_count,
                    model_name=conversation.model_name
                ),
                messages=[
                    MessageItem(
                        id=msg.id,
                        role=msg.role,
                        content=msg.content,
                        created_at=msg.created_at,
                        token_count=msg.token_count
                    )
                    for msg in messages
                ]
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting conversation history: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.exception_handler(Exception)
def generic_exception_handler(request: Request, exc: Exception):
    """Generic exception handler to prevent stack trace leakage."""
    print(f"Unhandled exception: {type(exc).__name__}: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"}
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=True
    )
