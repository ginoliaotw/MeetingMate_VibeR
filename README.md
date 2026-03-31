# MeetingMate — 離線會議記錄翻譯 App

將 WAV / MP3 / iPhone 語音備忘錄等音檔轉為逐字稿，再透過 LLM 自動產生結構化會議摘要，並備份至 Google Drive。

## 功能

- **離線語音轉文字** — 使用 [faster-whisper](https://github.com/SYSTRAN/faster-whisper)（基於 OpenAI Whisper large-v3），完全離線、支援中文/英文/日文
- **LLM 會議摘要** — 支援 ChatGPT / Claude / Gemini 三種 LLM，可在 App 內切換
- **摘要結構**：(a) 日期、主旨、參與者、200 字摘要 (b) 詳細摘要 (c) 待辦事項
- **Google Drive 備份** — 音檔 / 逐字稿 / 摘要一鍵同步至 Drive
- **支援格式** — WAV, MP3, M4A, CAF, AAC, OGG, FLAC（含 iPhone/Mac 語音備忘錄 .m4a/.caf）

## 快速開始

### 前置需求

- Python 3.10+
- ffmpeg（`brew install ffmpeg` 或 `apt install ffmpeg`）
- 至少一組 LLM API Key（OpenAI / Anthropic / Google）

### 安裝與啟動

```bash
cd MeetingMate
./start.sh
```

啟動後開啟瀏覽器前往 **http://localhost:8000**

### 手動啟動

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 設定

啟動後進入「設定」頁面：

1. **Whisper** — 選擇模型大小（small / medium / large-v3）、語言、運算裝置
2. **LLM** — 填入至少一組 API Key，選擇預設的摘要提供者
3. **Google Drive** — 放置 OAuth JSON 至 `data/gdrive_credentials.json`，透過 API 授權

### Google Drive 設定步驟

1. 前往 [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. 建立 OAuth 2.0 用戶端 ID（應用程式類型選「桌面應用程式」）
3. 下載 JSON 檔，重新命名為 `gdrive_credentials.json`
4. 放入 `data/` 目錄
5. 呼叫 `POST /api/gdrive/authorize` 開始授權流程

## 使用流程

1. **上傳** — 拖放或選擇音檔，填入會議標題/日期/參與者
2. **轉錄** — 點擊「開始轉錄」，Whisper 離線處理
3. **摘要** — 選擇 LLM（ChatGPT / Claude / Gemini），點擊「生成摘要」
4. **備份** — 點擊「備份至 Drive」，音檔+逐字稿+摘要同步上傳

## 專案結構

```
MeetingMate/
├── backend/
│   ├── main.py              # FastAPI 主程式
│   ├── config.py             # 設定管理
│   ├── database.py           # SQLAlchemy 模型
│   ├── whisper_engine.py     # Whisper 語音辨識引擎
│   ├── llm_engine.py         # LLM 摘要引擎
│   ├── gdrive_engine.py      # Google Drive 備份
│   └── requirements.txt      # Python 相依套件
├── frontend/
│   └── dist/
│       └── index.html        # React SPA（single-file）
├── data/                     # 執行時產生（含資料庫、音檔、逐字稿、摘要）
├── start.sh                  # 一鍵啟動腳本
└── README.md
```

## 技術棧

| 層級 | 技術 |
|------|------|
| 語音辨識 | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (large-v3) |
| 後端 | Python / FastAPI / SQLAlchemy / SQLite |
| 前端 | React 18 (CDN, single-file SPA) |
| LLM | OpenAI GPT-4o / Anthropic Claude / Google Gemini |
| 備份 | Google Drive API v3 (OAuth 2.0) |
