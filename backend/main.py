"""MeetingMate — FastAPI backend server (with WhisperX + speaker diarization).

Endpoints:
  POST   /api/meetings/upload                Upload audio & create meeting record
  GET    /api/meetings                        List all meetings
  GET    /api/meetings/{id}                   Get meeting detail
  DELETE /api/meetings/{id}                   Delete a meeting
  PUT    /api/meetings/{id}                   Update meeting title/date/participants
  POST   /api/meetings/{id}/transcribe        Start transcription (WhisperX + diarization)
  GET    /api/meetings/{id}/transcribe/progress  Get transcription progress (poll)
  POST   /api/meetings/{id}/transcribe/pause     Pause transcription
  POST   /api/meetings/{id}/transcribe/resume    Resume transcription
  POST   /api/meetings/{id}/transcribe/cancel    Cancel transcription
  POST   /api/meetings/{id}/summarize         Generate summary with chosen LLM
  PUT    /api/meetings/{id}/external-summary  Save externally generated summary
  POST   /api/meetings/{id}/backup            Backup to Google Drive
  GET    /api/settings                        Get app settings
  PUT    /api/settings                        Update app settings
  GET    /api/gdrive/status                   Check Google Drive auth status
  POST   /api/gdrive/authorize                Start Google Drive OAuth flow
"""

import os
import shutil
import json
import datetime
import logging
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, Depends, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import init_db, get_db, Meeting
from config import (
    load_settings, save_settings, Settings,
    UPLOADS_DIR, TRANSCRIPTS_DIR, SUMMARIES_DIR,
)
from whisper_engine import (
    get_job_progress, pause_job, resume_job, cancel_job, cleanup_job,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown."""
    init_db()
    logger.info("MeetingMate backend started.")
    yield
    logger.info("MeetingMate backend shutting down.")


app = FastAPI(title="MeetingMate", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Helpers ----------

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".caf", ".aac", ".ogg", ".flac", ".webm"}

def _allowed_file(filename: str) -> bool:
    return Path(filename).suffix.lower() in ALLOWED_EXTENSIONS


# ---------- Meetings CRUD ----------

@app.post("/api/meetings/upload")
async def upload_meeting(
    file: UploadFile = File(...),
    title: str = Form(""),
    date: str = Form(""),
    participants: str = Form(""),
    db: Session = Depends(get_db),
):
    """Upload audio file and create a meeting record."""
    if not file.filename or not _allowed_file(file.filename):
        raise HTTPException(400, f"Unsupported file format. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

    # Save file
    suffix = Path(file.filename).suffix.lower()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = f"meeting_{timestamp}{suffix}"
    dest = UPLOADS_DIR / safe_name

    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)

    # Get audio duration using pydub
    duration = 0.0
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(str(dest))
        duration = len(audio) / 1000.0
    except Exception as e:
        logger.warning(f"Could not read audio duration: {e}")

    meeting = Meeting(
        title=title or f"Meeting {timestamp}",
        date=date or datetime.date.today().isoformat(),
        participants=participants,
        audio_filename=file.filename,
        audio_path=str(dest),
        audio_duration_sec=duration,
        audio_format=suffix.lstrip("."),
        status="uploaded",
    )
    db.add(meeting)
    db.commit()
    db.refresh(meeting)

    return {"id": meeting.id, "status": "uploaded", "filename": safe_name, "duration": duration}


@app.get("/api/meetings")
def list_meetings(db: Session = Depends(get_db)):
    """List all meetings, newest first."""
    meetings = db.query(Meeting).order_by(Meeting.created_at.desc()).all()
    return [
        {
            "id": m.id,
            "title": m.title,
            "date": m.date,
            "participants": m.participants,
            "status": m.status,
            "audio_filename": m.audio_filename,
            "audio_duration_sec": m.audio_duration_sec,
            "created_at": m.created_at.isoformat() if m.created_at else "",
            "gdrive_synced": m.gdrive_synced,
            "summary_llm_provider": m.summary_llm_provider,
        }
        for m in meetings
    ]


@app.get("/api/meetings/{meeting_id}")
def get_meeting(meeting_id: int, db: Session = Depends(get_db)):
    """Get full meeting detail."""
    m = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not m:
        raise HTTPException(404, "Meeting not found")
    return {
        "id": m.id,
        "title": m.title,
        "date": m.date,
        "participants": m.participants,
        "status": m.status,
        "audio_filename": m.audio_filename,
        "audio_path": m.audio_path,
        "audio_duration_sec": m.audio_duration_sec,
        "audio_format": m.audio_format,
        "transcript_text": m.transcript_text,
        "transcript_language": m.transcript_language,
        "summary_brief": m.summary_brief,
        "summary_detailed": m.summary_detailed,
        "summary_action_items": m.summary_action_items,
        "summary_llm_provider": m.summary_llm_provider,
        "external_summary": m.external_summary,
        "transcript_speakers": json.loads(m.transcript_speakers) if m.transcript_speakers else [],
        "error_message": m.error_message,
        "created_at": m.created_at.isoformat() if m.created_at else "",
        "updated_at": m.updated_at.isoformat() if m.updated_at else "",
        "gdrive_synced": m.gdrive_synced,
    }


@app.delete("/api/meetings/{meeting_id}")
def delete_meeting(meeting_id: int, db: Session = Depends(get_db)):
    """Delete a meeting and its files."""
    m = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not m:
        raise HTTPException(404, "Meeting not found")

    # Remove files
    for p in [m.audio_path, m.transcript_path, m.summary_path]:
        if p and Path(p).exists():
            Path(p).unlink()

    db.delete(m)
    db.commit()
    return {"deleted": True}


# ---------- Transcription ----------

def _do_transcribe(meeting_id: int):
    """Background task: run WhisperX transcription with speaker diarization."""
    from database import SessionLocal
    from whisper_engine import transcribe

    db = SessionLocal()
    try:
        m = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not m:
            return

        m.status = "transcribing"
        db.commit()

        # Pass meeting_id so whisper_engine tracks progress/pause/cancel
        result = transcribe(m.audio_path, meeting_id=meeting_id)
        transcript_text = result["text"]
        language = result["language"]
        speakers = result.get("speakers", [])

        # Save transcript file
        transcript_filename = f"transcript_{m.id}.txt"
        transcript_path = TRANSCRIPTS_DIR / transcript_filename
        transcript_path.write_text(transcript_text, encoding="utf-8")

        # Also save segments as JSON (now includes speaker labels)
        segments_path = TRANSCRIPTS_DIR / f"segments_{m.id}.json"
        segments_path.write_text(json.dumps(result["segments"], ensure_ascii=False, indent=2), encoding="utf-8")

        # Save speakers list
        speakers_path = TRANSCRIPTS_DIR / f"speakers_{m.id}.json"
        speakers_path.write_text(json.dumps(speakers, ensure_ascii=False), encoding="utf-8")

        m.transcript_text = transcript_text
        m.transcript_language = language
        m.transcript_path = str(transcript_path)
        m.audio_duration_sec = result.get("duration", m.audio_duration_sec)
        m.transcript_speakers = json.dumps(speakers, ensure_ascii=False) if speakers else ""
        diarize_err = result.get("diarize_error", "")
        if diarize_err:
            m.error_message = f"說話者辨識失敗: {diarize_err}"
        else:
            m.error_message = ""
        m.status = "transcribed"
        db.commit()

    except InterruptedError:
        logger.info(f"Transcription cancelled for meeting {meeting_id}")
        m = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if m:
            m.status = "uploaded"  # reset to uploadable state
            m.error_message = ""
            db.commit()
    except Exception as e:
        logger.error(f"Transcription failed for meeting {meeting_id}: {e}", exc_info=True)
        m = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if m:
            m.status = "error"
            m.error_message = str(e)
            db.commit()
    finally:
        cleanup_job(meeting_id)
        db.close()


@app.post("/api/meetings/{meeting_id}/transcribe")
def transcribe_meeting(meeting_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Start transcription of a meeting's audio."""
    m = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not m:
        raise HTTPException(404, "Meeting not found")
    if not m.audio_path or not Path(m.audio_path).exists():
        raise HTTPException(400, "Audio file not found")

    m.status = "transcribing"
    db.commit()

    background_tasks.add_task(_do_transcribe, meeting_id)
    return {"status": "transcribing", "message": "Transcription started in background"}


@app.get("/api/meetings/{meeting_id}/transcribe/progress")
def transcribe_progress(meeting_id: int):
    """Get real-time transcription progress (poll this endpoint)."""
    return get_job_progress(meeting_id)


@app.post("/api/meetings/{meeting_id}/transcribe/pause")
def transcribe_pause(meeting_id: int):
    """Pause a running transcription."""
    pause_job(meeting_id)
    return {"status": "paused"}


@app.post("/api/meetings/{meeting_id}/transcribe/resume")
def transcribe_resume(meeting_id: int):
    """Resume a paused transcription."""
    resume_job(meeting_id)
    return {"status": "transcribing"}


@app.post("/api/meetings/{meeting_id}/transcribe/cancel")
def transcribe_cancel(meeting_id: int, db: Session = Depends(get_db)):
    """Cancel a running or paused transcription."""
    cancel_job(meeting_id)
    # Reset meeting status
    m = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if m and m.status in ("transcribing",):
        m.status = "uploaded"
        m.error_message = ""
        db.commit()
    return {"status": "cancelled"}


# ---------- Summary ----------

def _do_summarize(meeting_id: int, provider: str):
    """Background task: generate LLM summary."""
    from database import SessionLocal
    from llm_engine import summarize_transcript

    db = SessionLocal()
    try:
        m = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not m:
            return

        m.status = "summarizing"
        db.commit()

        result = summarize_transcript(m.transcript_text, m.transcript_language, provider)

        # Update meeting fields
        m.title = result.get("title", m.title) or m.title
        if result.get("date"):
            m.date = result["date"]
        if result.get("participants"):
            m.participants = result["participants"]
        m.summary_brief = result.get("brief_summary", "")
        m.summary_detailed = result.get("detailed_summary", "")
        m.summary_action_items = result.get("action_items", "")
        m.summary_llm_provider = provider

        # Save summary file
        summary_filename = f"summary_{m.id}.json"
        summary_path = SUMMARIES_DIR / summary_filename
        summary_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        m.summary_path = str(summary_path)

        m.status = "completed"
        db.commit()

    except Exception as e:
        logger.error(f"Summary failed for meeting {meeting_id}: {e}", exc_info=True)
        m = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if m:
            m.status = "error"
            m.error_message = str(e)
            db.commit()
    finally:
        db.close()


@app.post("/api/meetings/{meeting_id}/summarize")
def summarize_meeting(
    meeting_id: int,
    background_tasks: BackgroundTasks,
    provider: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """Generate meeting summary using selected LLM provider."""
    m = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not m:
        raise HTTPException(404, "Meeting not found")
    if not m.transcript_text:
        raise HTTPException(400, "No transcript available. Please transcribe first.")

    settings = load_settings()
    prov = provider or settings.llm_provider

    m.status = "summarizing"
    db.commit()

    background_tasks.add_task(_do_summarize, meeting_id, prov)
    return {"status": "summarizing", "provider": prov}


# ---------- Update Meeting Info ----------

@app.put("/api/meetings/{meeting_id}")
def update_meeting(meeting_id: int, data: dict, db: Session = Depends(get_db)):
    """Update meeting title, date, participants."""
    m = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not m:
        raise HTTPException(404, "Meeting not found")
    if "title" in data:
        m.title = data["title"]
    if "date" in data:
        m.date = data["date"]
    if "participants" in data:
        m.participants = data["participants"]
    db.commit()
    return {"status": "updated"}


# ---------- External Summary (pasted from external LLM) ----------

@app.put("/api/meetings/{meeting_id}/external-summary")
def save_external_summary(meeting_id: int, data: dict, db: Session = Depends(get_db)):
    """Save externally generated summary (pasted from ChatGPT/Claude/Gemini web)."""
    m = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not m:
        raise HTTPException(404, "Meeting not found")

    text = data.get("text", "").strip()
    m.external_summary = text

    # Save to file
    ext_filename = f"external_summary_{m.id}.txt"
    ext_path = SUMMARIES_DIR / ext_filename
    ext_path.write_text(text, encoding="utf-8")
    m.external_summary_path = str(ext_path)

    if m.status in ("transcribed", "uploaded"):
        m.status = "completed"
    db.commit()

    return {"status": "saved", "length": len(text)}


# ---------- Google Drive Backup ----------

def _make_drive_filename(meeting, suffix: str, ext: str) -> str:
    """Generate Drive filename: yyyy-mm-dd_標題_suffix.ext"""
    import re
    date_str = meeting.date or "undated"
    # Sanitize title for filename
    title = re.sub(r'[\\/:*?"<>|]', '_', meeting.title or "untitled")
    title = title.strip()[:60]  # limit length
    return f"{date_str}_{title}_{suffix}.{ext}"


def _do_backup(meeting_id: int):
    """Background task: upload files to Google Drive."""
    from database import SessionLocal
    from gdrive_engine import upload_file

    db = SessionLocal()
    try:
        m = db.query(Meeting).filter(Meeting.id == meeting_id).first()
        if not m:
            return

        # Upload audio
        if m.audio_path and Path(m.audio_path).exists():
            audio_ext = Path(m.audio_path).suffix.lstrip(".")
            fname = _make_drive_filename(m, "audio", audio_ext)
            file_id = upload_file(m.audio_path, filename=fname)
            m.gdrive_audio_id = file_id

        # Upload transcript
        if m.transcript_path and Path(m.transcript_path).exists():
            fname = _make_drive_filename(m, "transcript", "txt")
            file_id = upload_file(m.transcript_path, filename=fname)
            m.gdrive_transcript_id = file_id

        # Upload summary (API-generated)
        if m.summary_path and Path(m.summary_path).exists():
            fname = _make_drive_filename(m, "summary", "json")
            file_id = upload_file(m.summary_path, filename=fname)
            m.gdrive_summary_id = file_id

        # Upload external summary (pasted from external LLM)
        if m.external_summary_path and Path(m.external_summary_path).exists():
            fname = _make_drive_filename(m, "external_summary", "txt")
            file_id = upload_file(m.external_summary_path, filename=fname)
            m.gdrive_external_summary_id = file_id

        m.gdrive_synced = True
        db.commit()
        logger.info(f"Meeting {meeting_id} backed up to Google Drive.")

    except Exception as e:
        logger.error(f"Google Drive backup failed for meeting {meeting_id}: {e}", exc_info=True)
    finally:
        db.close()


@app.post("/api/meetings/{meeting_id}/backup")
def backup_meeting(meeting_id: int, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Backup meeting files to Google Drive."""
    m = db.query(Meeting).filter(Meeting.id == meeting_id).first()
    if not m:
        raise HTTPException(404, "Meeting not found")

    background_tasks.add_task(_do_backup, meeting_id)
    return {"status": "backing_up"}


# ---------- Settings ----------

@app.get("/api/settings")
def get_settings():
    """Get current app settings (API keys masked)."""
    s = load_settings()
    d = s.model_dump()
    # Mask API keys for security
    for key in ["openai_api_key", "anthropic_api_key", "gemini_api_key", "hf_token"]:
        if d.get(key):
            d[key] = d[key][:8] + "..." + d[key][-4:] if len(d[key]) > 12 else "***"
    return d


@app.get("/api/settings/raw")
def get_settings_raw():
    """Get settings with full API keys (for internal use only)."""
    return load_settings().model_dump()


@app.put("/api/settings")
def update_settings(data: dict):
    """Update app settings."""
    current = load_settings()
    current_dict = current.model_dump()

    # Only update provided fields; skip masked values
    for key, value in data.items():
        if key in current_dict and value and "..." not in str(value) and value != "***":
            current_dict[key] = value

    new_settings = Settings(**current_dict)
    save_settings(new_settings)
    return {"status": "saved"}


# ---------- Google Drive Auth ----------

@app.get("/api/gdrive/status")
def gdrive_status():
    """Check Google Drive authorization status."""
    try:
        from gdrive_engine import check_auth_status
        return check_auth_status()
    except Exception as e:
        return {"authorized": False, "email": "", "error": str(e)}


@app.post("/api/gdrive/authorize")
def gdrive_authorize():
    """Start Google Drive OAuth flow (opens browser for consent)."""
    try:
        from gdrive_engine import start_auth_flow
        result = start_auth_flow()
        return result
    except Exception as e:
        return {"success": False, "error": str(e)}


# ---------- Serve Frontend (production) ----------

frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
