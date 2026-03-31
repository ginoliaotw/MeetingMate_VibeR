#!/bin/bash
# MeetingMate — Quick Start Script
# Usage: ./start.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
DATA_DIR="$SCRIPT_DIR/data"

echo "🎙️  MeetingMate — 離線會議記錄翻譯 App"
echo "========================================="
echo ""

# Create data directories
mkdir -p "$DATA_DIR"/{uploads,transcripts,summaries}

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.10+."
    exit 1
fi

# Check ffmpeg (required by Whisper)
if ! command -v ffmpeg &> /dev/null; then
    echo "⚠️  ffmpeg not found. Installing..."
    if command -v brew &> /dev/null; then
        brew install ffmpeg
    elif command -v apt-get &> /dev/null; then
        sudo apt-get install -y ffmpeg
    else
        echo "❌ Please install ffmpeg manually: https://ffmpeg.org/download.html"
        exit 1
    fi
fi

# Create venv if needed
VENV_DIR="$SCRIPT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"

# Upgrade pip + setuptools first (fixes pkg_resources / build wheel errors)
echo "📦 Upgrading pip & setuptools..."
pip install -q --upgrade pip setuptools wheel

# Install deps
echo "📦 Installing dependencies..."
pip install -q -r "$BACKEND_DIR/requirements.txt"

echo ""
echo "🚀 Starting MeetingMate server at http://localhost:8000"
echo "   Frontend: http://localhost:8000"
echo "   API docs: http://localhost:8000/docs"
echo ""
echo "   Press Ctrl+C to stop."
echo ""

cd "$BACKEND_DIR"
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
