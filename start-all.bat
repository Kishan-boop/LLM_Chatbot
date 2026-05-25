@echo off
REM Start All Services Script for Windows
REM Runs ingestion service, chatbot service, and frontend concurrently

echo Starting LLM Inference Logger...
echo.

if "%INGESTION_API_URL%"=="" set INGESTION_API_URL=http://localhost:8001/api/ingest
if "%FRONTEND_PORT%"=="" set FRONTEND_PORT=5174

echo Starting Ingestion Service (port 8001)...
start "Ingestion Service" cmd /k "cd backend\ingestion-service && (if not exist venv python -m venv venv) && venv\Scripts\activate && pip install -q -r requirements.txt && python main.py"

timeout /t 3 /nobreak >nul

echo Starting Chatbot Service (port 8000)...
start "Chatbot Service" cmd /k "cd backend\chatbot-service && (if not exist venv python -m venv venv) && venv\Scripts\activate && pip install -q -r requirements.txt && set INGESTION_API_URL=%INGESTION_API_URL%&& python main.py"

timeout /t 3 /nobreak >nul

echo Starting Frontend (port %FRONTEND_PORT%)...
start "Frontend" cmd /k "cd frontend && (if not exist node_modules npm install) && set FRONTEND_PORT=%FRONTEND_PORT%&& npm run dev"

echo.
echo All services started!
echo.
echo Access the application:
echo   Frontend:  http://localhost:%FRONTEND_PORT%
echo   Chatbot:   http://localhost:8000/docs
echo   Ingestion: http://localhost:8001/docs
echo.
echo Close the terminal windows to stop services
echo.
pause
