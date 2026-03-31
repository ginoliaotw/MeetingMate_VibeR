#!/usr/bin/env bash
# MeetingMate — 啟動腳本
# 開發模式：直接執行此腳本
# 正式打包：npm run build  →  release/ 目錄下的 .dmg / .app

set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT/backend"
DATA_DIR="$ROOT/data"

echo "🎙️  MeetingMate — 離線會議記錄翻譯 App"
echo "========================================="

# 建立資料目錄
mkdir -p "$DATA_DIR"/{uploads,transcripts,summaries}

# 確認 Python
if ! command -v python3 &>/dev/null; then
  echo "❌ 找不到 Python 3，請安裝 Python 3.10+"; exit 1
fi

# 確認 ffmpeg
if ! command -v ffmpeg &>/dev/null; then
  echo "⚠️  安裝 ffmpeg..."
  brew install ffmpeg 2>/dev/null || { echo "❌ 請手動安裝 ffmpeg"; exit 1; }
fi

# Python 虛擬環境
VENV_DIR="$ROOT/.venv"
if [ ! -d "$VENV_DIR" ]; then
  echo "📦 建立 Python 虛擬環境..."
  python3 -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"

echo "📦 確認 Python 套件..."
pip install -q --upgrade pip setuptools wheel
pip install -q -r "$BACKEND_DIR/requirements.txt"

# Node / Electron
if ! command -v node &>/dev/null; then
  echo "❌ 找不到 Node.js，請安裝 Node.js 18+"; exit 1
fi

if [ ! -d "$ROOT/node_modules" ]; then
  echo "📦 安裝 Electron 依賴..."
  cd "$ROOT" && npm install
fi

echo ""
echo "🚀 以 Electron 桌面模式啟動 MeetingMate..."
echo "   （如需純後端模式，請改用：uvicorn main:app --port 8000）"
echo ""

cd "$ROOT" && npx electron .
