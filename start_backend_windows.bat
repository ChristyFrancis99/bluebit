@echo off
echo ========================================
echo  Academic Integrity - Backend Startup
echo ========================================
echo.

cd /d "%~dp0"

echo [1/3] Installing dependencies (pre-built wheels only)...
python -m pip install --upgrade pip --quiet
python -m pip install --only-binary=:all: scikit-learn numpy
python -m pip install fastapi "uvicorn[standard]" python-multipart pydantic pydantic-settings "sqlalchemy[asyncio]" aiosqlite alembic redis fakeredis datasketch boto3 "python-jose[cryptography]" "passlib[bcrypt]" bcrypt python-docx PyPDF2 chardet reportlab aiofiles httpx structlog langdetect

echo.
echo [2/3] Checking .env file...
if not exist .env (
  copy .env.example .env
  echo Created .env from template
)

echo.
echo [3/3] Starting backend...
echo   API:  http://localhost:8000
echo   Docs: http://localhost:8000/api/docs
echo.
python -m uvicorn api.main:app --reload --port 8000 --host 127.0.0.1

pause
