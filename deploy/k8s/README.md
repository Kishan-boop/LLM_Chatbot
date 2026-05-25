# Self-Hosted Kubernetes Deployment

This manifest deploys the full stack: frontend, chatbot API, ingestion API, Redis Streams, SQLite PVCs, health probes, resource limits, NodePort access, and an optional nginx Ingress.

## Build Images

For a single-node cluster such as Docker Desktop, kind, k3s, or minikube:

```bash
docker build -t llm-logger-chatbot:latest backend/chatbot-service
docker build -t llm-logger-ingestion:latest backend/ingestion-service
docker build -t llm-logger-frontend:latest frontend
```

For a remote cluster, push these images to your registry and update `image:` in `app.yaml`.

## Configure Secrets

Edit `app.yaml` and replace:

- `OPENAI_API_KEY`
- `SECRET_KEY`
- `GROQ_API_KEY` if you want Groq fallback

The default config uses OpenRouter-compatible OpenAI settings:

```yaml
LLM_PROVIDER: openai
DEFAULT_MODEL: openrouter/free
OPENAI_BASE_URL: https://openrouter.ai/api/v1
```

## Deploy

```bash
kubectl apply -f deploy/k8s/app.yaml
kubectl -n llm-logger rollout status deploy/redis
kubectl -n llm-logger rollout status deploy/ingestion
kubectl -n llm-logger rollout status deploy/chatbot
kubectl -n llm-logger rollout status deploy/frontend
```

Open the app through NodePort:

```text
http://<node-ip>:30173
```

For local clusters, this is often:

```text
http://localhost:30173
```

## Optional Ingress

If you run nginx ingress, map `llm-logger.local` to your cluster ingress IP in `/etc/hosts` or Windows hosts file, then open:

```text
http://llm-logger.local
```

SSE streaming needs long proxy timeouts; the included Ingress annotations set those.
