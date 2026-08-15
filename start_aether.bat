@echo off
echo ============================================
echo   AETHER - Starting Services
echo ============================================
echo.

echo Starting Backend (uvicorn on port 8000)...
start cmd /k "conda activate aether && uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000"

echo Waiting for backend startup...
timeout /t 5 /nobreak >nul

echo Starting Frontend (Vite on port 5173)...
start cmd /k "cd frontend && npm run dev"

echo.
echo ============================================
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo   API Docs: http://localhost:8000/docs
echo ============================================
echo.
pause
