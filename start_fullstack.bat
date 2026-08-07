@echo off
echo Starting EdgeVision Fullstack...

REM Initialize the SQLite database if it doesn't exist
echo Initializing database...
python database/init_db.py

REM Start the backend in a new command prompt window
echo Starting FastAPI Backend...
start "Backend (FastAPI)" cmd /c "python -m src.api.server"

REM Give the backend a few seconds to start
timeout /t 3 /nobreak >nul

REM Start the frontend in the current window
echo Starting React Frontend...
cd frontend
call npm install
call npm run dev
