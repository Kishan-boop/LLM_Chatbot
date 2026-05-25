#!/bin/bash

# Start all services for local development.

echo "Starting LLM Inference Logger..."
echo ""

cleanup() {
    echo ""
    echo "Stopping all services..."
    kill $(jobs -p) 2>/dev/null
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "Starting Ingestion Service (port 8001)..."
cd backend/ingestion-service || exit 1
if [ ! -d "venv" ]; then
    python -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
python main.py &
cd ../.. || exit 1

sleep 2

echo "Starting Chatbot Service (port 8000)..."
cd backend/chatbot-service || exit 1
if [ ! -d "venv" ]; then
    python -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt
export INGESTION_API_URL="${INGESTION_API_URL:-http://localhost:8001/api/ingest}"
python main.py &
cd ../.. || exit 1

sleep 2

export FRONTEND_PORT="${FRONTEND_PORT:-5174}"
echo "Starting Frontend (port ${FRONTEND_PORT})..."
cd frontend || exit 1
if [ ! -d "node_modules" ]; then
    npm install
fi
npm run dev &
cd .. || exit 1

echo ""
echo "All services started."
echo "Frontend:  http://localhost:${FRONTEND_PORT}"
echo "Chatbot:   http://localhost:8000/docs"
echo "Ingestion: http://localhost:8001/docs"
echo ""
echo "Press Ctrl+C to stop all services."

wait
