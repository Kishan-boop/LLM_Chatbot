# Architecture Notes

## Ingestion Flow

1. The browser sends `POST /api/chat` to the chatbot service.
2. The chatbot service creates or resumes a conversation and stores the user message.
3. `LoggingLLMClient` calls the configured provider (`mock` locally, `openai` for GPT, or `groq`).
4. The wrapper measures latency, captures token usage, timestamps, provider/model, status, errors, and redacted previews.
5. The wrapper publishes the metadata to Redis Streams.
6. The ingestion service consumes the stream, validates the payload, redacts previews again, and stores the processed log.
7. The frontend polls `/ingestion-api/metrics` for lightweight dashboard data.

## Logging Strategy

Logs are structured JSON records with stable identifiers:

- `conversation_id` links model calls to chat sessions.
- `message_id` links the inference call to the assistant message when available.
- `provider` and `model` enable multi-provider analytics.
- `latency_ms`, token counts, and `status` power dashboards.
- `input_preview` and `output_preview` are truncated and PII-redacted.

The chat response does not wait for ingestion to finish. Redis Streams decouple chat latency from telemetry persistence and allow the ingestion worker to recover after short outages.

## Scaling Considerations

- Move SQLite to Postgres for concurrent writes and long-term retention.
- Add a dead-letter stream and replay tooling for failed Redis Stream events.
- Partition `inference_logs` by time for high-volume analytics.
- Add separate read models/materialized views for dashboards.
- Run chatbot and ingestion services as independently scaled deployments.
- Add more provider adapters so Anthropic, Gemini, DeepSeek, and other APIs share the same logging contract.

## Failure Handling Assumptions

- Ingestion is event based through Redis Streams.
- If ingestion is down, the chat request still succeeds and queued events remain in Redis.
- If Redis is unavailable, the chat request still succeeds and the publish failure is printed server-side.
- Provider failures are logged as `status=error` when possible and returned to the API as a generic backend error.
- Frontend cancellation aborts the streaming HTTP request from the browser.

## Deployment Notes

`docker-compose.yml` starts Redis, the frontend, chatbot service, and ingestion service with persistent Docker volumes for SQLite files. Kubernetes manifests include Secrets for API keys, ConfigMaps for service URLs, readiness/liveness probes, resource requests/limits, NodePort, and optional nginx Ingress.
