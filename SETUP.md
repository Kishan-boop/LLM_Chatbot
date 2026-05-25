# Setup Guide

## Prerequisites Check

Before starting, ensure you have:

```bash
# Check Python version (need 3.11+)
python --version

# Check Node.js version (need 20+)
node --version

# Check npm
npm --version
```

## Step-by-Step Setup

### 1. Get Groq API Key

1. Go to https://console.groq.com
2. Sign up with your email (no credit card required)
3. Click on "API Keys" in the sidebar
4. Click "Create API Key"
5. Give it a name (e.g., "LLM Logger")
6. Copy the key (starts with `gsk_...`)

**Free Tier Limits:**
- 14,400 requests per day
- 10 requests per minute
- No credit card required

### 2. Configure Environment

```bash
# Navigate to chatbot service
cd backend/chatbot-service

# Copy example config
cp .env.example .env

# Edit .env and add your API key
# On Windows: notepad .env
# On Mac/Linux: nano .env
```

Add this line with your actual key:
```
GROQ_API_KEY=gsk_your_actual_key_here
```

### 3. Install Dependencies

#### Option A: Automatic (Recommended)

**Windows:**
```bash
# Double-click start-all.bat
# Or run from command prompt:
start-all.bat
```

**Mac/Linux:**
```bash
# Make script executable
chmod +x start-all.sh

# Run script
./start-all.sh
```

#### Option B: Manual

**Ingestion Service:**
```bash
cd backend/ingestion-service
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

**Chatbot Service (in new terminal):**
```bash
cd backend/chatbot-service
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

**Frontend (in new terminal):**
```bash
cd frontend
npm install
npm run dev
```

### 4. Verify Installation

Open http://localhost:5173 in your browser.

You should see:
- Chat interface with purple gradient background
- "LLM Chatbot" header
- Text input box at the bottom
- "New Chat" button

### 5. Test the System

1. Type: "Hello, what can you help me with?"
2. Press Enter
3. Wait 1-2 seconds for response
4. Verify: You get a response from the LLM
5. Send another message to test context preservation

### 6. Verify Logging

```bash
# Check if databases were created
ls backend/chatbot-service/chatbot.db
ls backend/ingestion-service/ingestion.db

# Query logs
sqlite3 backend/chatbot-service/chatbot.db "SELECT COUNT(*) FROM messages;"
sqlite3 backend/ingestion-service/ingestion.db "SELECT COUNT(*) FROM inference_logs;"
```

You should see message counts matching your conversation.

## Common Issues

### "GROQ_API_KEY must be set"
- **Fix:** Edit `backend/chatbot-service/.env` and add your API key

### "Module not found" errors
- **Fix:** Ensure you activated the virtual environment before pip install
```bash
source venv/bin/activate  # Mac/Linux
venv\Scripts\activate     # Windows
```

### "Port already in use"
- **Fix:** Stop any services running on ports 8000, 8001, or 5173
```bash
# Find process using port
lsof -i :8000  # Mac/Linux
netstat -ano | findstr :8000  # Windows

# Kill process
kill -9 <PID>  # Mac/Linux
taskkill /PID <PID> /F  # Windows
```

### Frontend can't connect to backend
- **Fix:** Ensure both backend services are running first
- **Check:** http://localhost:8000/health should return `{"status": "ok"}`

### "CSRF token missing"
- **Fix:** Refresh the browser page (F5)

## Development Tips

### Run Services Separately

For development, you may want to run each service in its own terminal:

**Terminal 1 - Ingestion Service:**
```bash
cd backend/ingestion-service
source venv/bin/activate
uvicorn main:app --port 8001 --reload
```

**Terminal 2 - Chatbot Service:**
```bash
cd backend/chatbot-service
source venv/bin/activate
uvicorn main:app --port 8000 --reload
```

**Terminal 3 - Frontend:**
```bash
cd frontend
npm run dev
```

### View API Documentation

FastAPI auto-generates interactive API docs:

- Chatbot API: http://localhost:8000/docs
- Ingestion API: http://localhost:8001/docs

You can test endpoints directly from the browser!

### Monitor Logs

Each service prints logs to its terminal:
- **Ingestion Service:** Log ingestion success/failures
- **Chatbot Service:** API requests, LLM calls, errors
- **Frontend:** Vite dev server logs, hot reload

### Database Inspection

```bash
# Open database
sqlite3 backend/chatbot-service/chatbot.db

# Useful queries
.tables                          # List all tables
.schema conversations            # Show table structure
SELECT * FROM conversations;     # View conversations
SELECT * FROM messages LIMIT 5;  # View recent messages

# Analytics query
SELECT
  AVG(latency_ms) as avg_latency,
  COUNT(*) as total_calls,
  SUM(total_tokens) as total_tokens
FROM inference_logs;

# Exit
.quit
```

## Next Steps

Once everything is running:

1. **Test multi-turn conversations** - Ask follow-up questions
2. **Try different prompts** - Creative writing, coding, analysis
3. **Check the database** - Inspect logged inference data
4. **Read the code** - Understand security patterns used
5. **Extend the system** - Add features like user auth, export, etc.

## Production Deployment

For production, consider:

1. **Use PostgreSQL** instead of SQLite
2. **Add authentication** (JWT tokens)
3. **Enable HTTPS** (SSL certificates)
4. **Add monitoring** (Prometheus, Grafana)
5. **Deploy behind reverse proxy** (Nginx)
6. **Use environment-specific configs**
7. **Set up CI/CD** (GitHub Actions, etc.)

See README.md for detailed deployment recommendations.

## Getting Help

If you're stuck:

1. Check the **Troubleshooting** section in README.md
2. Review error messages carefully
3. Verify all prerequisites are installed
4. Ensure API key is valid and has quota
5. Check firewall/antivirus isn't blocking localhost

Happy coding!
