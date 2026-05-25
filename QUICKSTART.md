# Quick Start Guide

Get the LLM chatbot running in 5 minutes!

## Prerequisites

- Python 3.11+
- Node.js 20+
- Groq API key (free at https://console.groq.com)

## 3-Step Setup

### 1. Get API Key (2 minutes)

Visit https://console.groq.com → Sign up → Create API Key → Copy it

### 2. Configure (1 minute)

```bash
cd backend/chatbot-service
cp .env.example .env
# Edit .env and paste your API key
```

### 3. Run (2 minutes)

**Windows:**
```bash
start-all.bat
```

**Mac/Linux:**
```bash
chmod +x start-all.sh
./start-all.sh
```

## Access

Open http://localhost:5173 in your browser.

## First Conversation

1. Type: "Tell me a joke about programming"
2. Press Enter
3. Wait ~1 second
4. Enjoy the response!

## What's Running?

- **Frontend** (port 5173) - React chat UI
- **Chatbot** (port 8000) - FastAPI backend
- **Ingestion** (port 8001) - Log collection service

## API Documentation

- Chatbot API: http://localhost:8000/docs
- Ingestion API: http://localhost:8001/docs

## Check the Logs

```bash
sqlite3 backend/chatbot-service/chatbot.db
SELECT * FROM messages;
.quit
```

## Troubleshooting

**"Invalid API key"** → Check .env file has correct key

**"Port already in use"** → Stop any services on ports 8000/8001/5173

**"CSRF token missing"** → Refresh the browser page

## Next Steps

- Read [SETUP.md](SETUP.md) for detailed installation
- Check [README.md](README.md) for full documentation
- Review [ARCHITECTURE.md](ARCHITECTURE.md) for system design

## Stop Services

Press `Ctrl+C` in the terminal or close the command windows.

---

**Happy chatting!** 🤖
