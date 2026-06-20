@echo off
chcp 65001 >nul
cd /d "%~dp0"

start "Solo Asset Manager Backend" cmd /k "backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload"
start "Solo Asset Manager Frontend" cmd /k "cd frontend && npm run dev"
