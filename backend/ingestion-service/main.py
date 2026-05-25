"""
Ingestion Service - Receives and stores LLM inference logs.
FastAPI application for log ingestion with validation and rate limiting.
"""
import secrets
import re
import json
import threading
import time
from datetime import datetime
from datetime import timedelta
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import func
import redis
from redis.exceptions import ResponseError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import settings
from database import init_database, get_db, InferenceLog
from models import InferenceLogPayload, IngestResponse, ErrorResponse

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create FastAPI app
app = FastAPI(
    title="LLM Inference Ingestion Service",
    description="Receives and stores inference logs from LLM SDK wrapper",
    version="1.0.0"
)

# Add rate limiter to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.on_event("startup")
def startup_event():
    """Initialize database on startup."""
    init_database()
    start_stream_worker()
    print(f"Ingestion service started on {settings.host}:{settings.port}")
    print(f"Database: {settings.database_path}")


@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "ingestion", "timestamp": datetime.utcnow().isoformat()}


def redact_preview(value: str | None) -> str | None:
    """Redact common PII patterns before persistence."""
    if value is None:
        return None
    redacted = re.sub(r'[\w.+-]+@[\w-]+\.[\w.-]+', '[redacted-email]', value)
    redacted = re.sub(r'\b(?:\+?\d[\d\s().-]{7,}\d)\b', '[redacted-phone]', redacted)
    redacted = re.sub(r'\b(?:\d[ -]*?){13,16}\b', '[redacted-card]', redacted)
    return redacted


def store_inference_log(payload: InferenceLogPayload) -> str:
    """Validate and persist one inference log payload."""
    log_id = secrets.token_urlsafe(16)
    log_entry = InferenceLog(
        id=log_id,
        conversation_id=payload.conversation_id,
        message_id=payload.message_id,
        provider=payload.provider,
        model=payload.model,
        request_timestamp=payload.request_timestamp,
        response_timestamp=payload.response_timestamp,
        latency_ms=payload.latency_ms,
        prompt_tokens=payload.prompt_tokens or 0,
        completion_tokens=payload.completion_tokens or 0,
        total_tokens=payload.total_tokens or 0,
        status=payload.status,
        error_message=payload.error_message,
        input_preview=redact_preview(payload.input_preview),
        output_preview=redact_preview(payload.output_preview),
        created_at=datetime.utcnow().isoformat()
    )

    with get_db() as db:
        db.add(log_entry)
        db.commit()

    return log_id


def start_stream_worker() -> None:
    """Start a background Redis Streams consumer for inference log events."""
    worker = threading.Thread(target=consume_inference_stream, daemon=True)
    worker.start()


def consume_inference_stream() -> None:
    """Consume inference log events from Redis Streams and persist them."""
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    stream = settings.inference_log_stream
    group = settings.inference_consumer_group
    consumer = settings.inference_consumer_name

    while True:
        try:
            try:
                client.xgroup_create(stream, group, id="0", mkstream=True)
            except ResponseError as exc:
                if "BUSYGROUP" not in str(exc):
                    raise

            events = client.xreadgroup(
                groupname=group,
                consumername=consumer,
                streams={stream: ">"},
                count=25,
                block=settings.stream_block_ms,
            )

            for _, messages in events:
                for message_id, fields in messages:
                    try:
                        payload = InferenceLogPayload.model_validate(json.loads(fields["payload"]))
                        store_inference_log(payload)
                        client.xack(stream, group, message_id)
                    except Exception as exc:
                        print(f"Failed to process inference event {message_id}: {exc}")
        except Exception as exc:
            print(f"Redis stream consumer unavailable: {exc}")
            time.sleep(3)


@app.post("/api/ingest", response_model=IngestResponse, responses={
    429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
    422: {"model": ErrorResponse, "description": "Validation error"},
    500: {"model": ErrorResponse, "description": "Internal server error"}
})
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
def ingest_log(payload: InferenceLogPayload, request: Request):
    """
    Ingest inference log from LLM SDK wrapper.

    Validates payload, generates log ID, and stores in database.
    Rate limited to prevent abuse.
    """
    try:
        log_id = store_inference_log(payload)

        return IngestResponse(
            success=True,
            log_id=log_id,
            message="Log ingested successfully"
        )

    except Exception as e:
        # Log error internally but don't expose details to client
        print(f"Error ingesting log: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error"
        )


@app.get("/api/metrics")
def get_metrics():
    """Return lightweight operational metrics for dashboards."""
    try:
        with get_db() as db:
            total = db.query(func.count(InferenceLog.id)).scalar() or 0
            errors = db.query(func.count(InferenceLog.id)).filter(InferenceLog.status != "success").scalar() or 0
            avg_latency = db.query(func.avg(InferenceLog.latency_ms)).scalar() or 0
            total_tokens = db.query(func.sum(InferenceLog.total_tokens)).scalar() or 0
            one_minute_ago = (datetime.utcnow() - timedelta(minutes=1)).isoformat()
            recent_requests = db.query(func.count(InferenceLog.id)).filter(
                InferenceLog.created_at >= one_minute_ago
            ).scalar() or 0
            by_provider = db.query(
                InferenceLog.provider,
                InferenceLog.model,
                func.count(InferenceLog.id).label("requests"),
                func.avg(InferenceLog.latency_ms).label("avg_latency_ms"),
                func.sum(InferenceLog.total_tokens).label("tokens")
            ).group_by(InferenceLog.provider, InferenceLog.model).all()

            return {
                "total_requests": total,
                "error_count": errors,
                "error_rate": (errors / total) if total else 0,
                "avg_latency_ms": int(avg_latency or 0),
                "total_tokens": int(total_tokens or 0),
                "throughput_per_minute": int(recent_requests),
                "providers": [
                    {
                        "provider": row.provider,
                        "model": row.model,
                        "requests": row.requests,
                        "avg_latency_ms": int(row.avg_latency_ms or 0),
                        "tokens": int(row.tokens or 0),
                    }
                    for row in by_provider
                ],
            }

    except Exception as e:
        print(f"Error building metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/logs")
def list_logs(limit: int = 50):
    """Return recent inference logs for inspection."""
    try:
        with get_db() as db:
            logs = db.query(InferenceLog).order_by(
                InferenceLog.created_at.desc()
            ).limit(min(limit, 200)).all()

            return [
                {
                    "id": log.id,
                    "conversation_id": log.conversation_id,
                    "message_id": log.message_id,
                    "provider": log.provider,
                    "model": log.model,
                    "latency_ms": log.latency_ms,
                    "prompt_tokens": log.prompt_tokens,
                    "completion_tokens": log.completion_tokens,
                    "total_tokens": log.total_tokens,
                    "status": log.status,
                    "error_message": log.error_message,
                    "input_preview": log.input_preview,
                    "output_preview": log.output_preview,
                    "created_at": log.created_at,
                }
                for log in logs
            ]

    except Exception as e:
        print(f"Error listing logs: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.exception_handler(Exception)
def generic_exception_handler(request: Request, exc: Exception):
    """
    Generic exception handler to prevent stack trace leakage.
    Returns generic error message to client.
    """
    # Log error internally for debugging
    print(f"Unhandled exception: {type(exc).__name__}: {str(exc)}")

    # Return generic error to client (security best practice)
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
        reload=True  # Enable auto-reload in development
    )
