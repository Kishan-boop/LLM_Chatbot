# LLM Inference Logger

A lightweight chatbot plus inference logging and ingestion system. It includes a React UI, a FastAPI chatbot service, a small LLM wrapper/SDK, a FastAPI ingestion API, SQLite storage, and a live metrics panel.

## What Is Included

- Multi-turn chatbot UI with short context memory.
- Conversation list, resume, delete, and in-flight request cancellation.
- LLM wrapper that records provider, model, latency, tokens, timestamps, status, errors, conversation ID, and redacted input/output previews.
- Server-Sent Events streaming responses from FastAPI to React.
- Event-based log ingestion over Redis Streams, plus a compatibility HTTP ingest endpoint.
- SQLite schemas for conversations, messages, and inference logs.
- Metrics dashboard for request count, latency, token throughput, provider usage, and errors.
- Docker Compose one-command local setup, including Redis.
- Self-hosted Kubernetes manifests in `deploy/k8s` with Secrets, ConfigMaps, probes, resources, NodePort, and optional Ingress.
- Local `mock` provider for demos without an API key, plus OpenAI/GPT and Groq support for real LLM calls.

## Quick Start

Run the complete stack with Docker:

```bash
cp .env.example .env
docker compose up --build
```

Open:

- Frontend: http://localhost:5174
- Chatbot API docs: http://localhost:8000/docs
- Ingestion API docs: http://localhost:8001/docs

The default Docker fallback `LLM_PROVIDER=mock` works without external credentials. To use OpenAI/GPT, edit `.env`:

```bash
LLM_PROVIDER=openai
DEFAULT_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk_your_openai_key_here
```

OpenAI API usage requires an OpenAI platform API key and may require billing/credits on your account. A ChatGPT web subscription is not the same thing as API access.

To use Groq instead:

```bash
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_key_here
```

## Manual Setup

In one terminal:

```bash
cd backend/ingestion-service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8001
```

In a second terminal:

```bash
cd backend/chatbot-service
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
set LLM_PROVIDER=mock
set INGESTION_API_URL=http://localhost:8001/api/ingest
uvicorn main:app --host 0.0.0.0 --port 8000
```

In a third terminal:

```bash
cd frontend
npm install
npm run dev
```

On PowerShell, use `$env:LLM_PROVIDER="mock"` instead of `set`.

## Architecture Overview

`frontend` sends chat requests to `chatbot-service`. The chatbot service persists user and assistant messages, builds a short conversation context, calls the configured LLM provider through `LoggingLLMClient`, and returns the assistant response.

`LoggingLLMClient` supports `mock`, `openai`, and `groq` through provider adapters. It can stream tokens, fall back to configured providers, measures latency, extracts token usage, records status/errors, redacts common PII in previews, and publishes structured log events to Redis Streams.

`ingestion-service` consumes Redis Stream events, validates each payload with Pydantic, redacts previews again as a defensive layer, stores the processed log, and exposes dashboard metrics. Its HTTP ingest endpoint remains for compatibility and manual testing.

## Schema Design

- `conversations`: one row per chat session, with timestamps, model name, and context window size.
- `messages`: normalized chat messages linked to a conversation, with role, content, timestamp, and estimated token count.
- `inference_logs`: one row per model call, optimized for analytics with indexes on conversation, time/status, and provider/model.

SQLite keeps the demo lightweight and easy to run. For production, this schema maps cleanly to Postgres with the same indexes and a migration tool such as Alembic.

## Tradeoffs

- Log delivery is event-based through Redis Streams. For production, add persistent Redis storage policies and dead-letter handling for poison events.
- Streaming is implemented with SSE; proxy/read timeouts must allow long-lived responses in production.
- The mock provider is deterministic and useful for demos/tests, but real quality requires `LLM_PROVIDER=groq`.
- SQLite is simple and portable, but write-heavy production use should move to Postgres.

## Improvements With More Time

- Add a dead-letter stream and replay tooling for failed ingestion events.
- Add Anthropic, Gemini, and DeepSeek adapters behind the same provider interface.
- Add auth, user-scoped conversations, and tenant-aware rate limits.
- Add production-grade Kubernetes HPA, managed Postgres, and queue-based ingestion.

## Demo

Run `docker compose up --build`, open http://localhost:5173, send a few messages, and watch the sidebar update conversations and metrics in near real time.
