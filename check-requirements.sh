#!/bin/bash

# Lightweight prerequisite checker for local development.

echo "Checking system requirements..."
echo ""

ERRORS=0

check_command() {
    NAME=$1
    COMMAND=$2

    echo -n "$NAME: "
    if command -v "$COMMAND" >/dev/null 2>&1; then
        echo "OK ($($COMMAND --version 2>&1 | head -n 1))"
    else
        echo "Missing"
        ERRORS=$((ERRORS + 1))
    fi
}

check_python() {
    PYTHON_BIN=$1
    if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
        return 1
    fi

    VERSION=$($PYTHON_BIN -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    MAJOR=$(echo "$VERSION" | cut -d. -f1)
    MINOR=$(echo "$VERSION" | cut -d. -f2)

    if [ "$MAJOR" -gt 3 ] || { [ "$MAJOR" -eq 3 ] && [ "$MINOR" -ge 11 ]; }; then
        echo "Python: OK ($($PYTHON_BIN --version 2>&1))"
        return 0
    fi

    echo "Python: Found $VERSION, need 3.11+"
    return 1
}

if ! check_python python3 && ! check_python python; then
    ERRORS=$((ERRORS + 1))
fi

check_command "Node.js" node
check_command "npm" npm

echo ""
echo "Checking Docker Compose..."
echo -n "Docker: "
if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    echo "OK ($(docker compose version))"
else
    echo "Missing or Compose plugin unavailable (optional if using manual setup)"
fi

echo ""
echo "Checking common ports..."

check_port() {
    PORT=$1
    NAME=$2
    if command -v lsof >/dev/null 2>&1 && lsof -Pi :"$PORT" -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "Port $PORT ($NAME): In use"
    else
        echo "Port $PORT ($NAME): Available or unable to verify"
    fi
}

check_port 8000 "Chatbot Service"
check_port 8001 "Ingestion Service"
check_port 5173 "Frontend"

echo ""
echo "Configuration:"
if [ -f ".env" ]; then
    echo ".env: Found"
    if grep -q "LLM_PROVIDER=openai" .env && grep -q "OPENAI_API_KEY=your_openai_api_key_here" .env; then
        echo "OPENAI_API_KEY: Placeholder value still set"
    fi
else
    echo ".env: Missing. Run: cp .env.example .env"
fi

if [ $ERRORS -eq 0 ]; then
    echo ""
    echo "All required checks passed."
    echo "Run: docker compose up --build"
    exit 0
fi

echo ""
echo "$ERRORS required check(s) failed."
exit 1
