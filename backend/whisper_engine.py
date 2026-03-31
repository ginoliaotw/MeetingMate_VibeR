"""Offline speech-to-text using WhisperX (faster-whisper + pyannote speaker diarization).

WhisperX provides:
  - Fast transcription via faster-whisper (CTranslate2 backend)
  - Word-level timestamps via forced alignment (wav2vec2)
  - Speaker diarization via pyannote-audio
  - Lower diarization error rate (~8% DER) than pyannote alone

Features:
  - Real-time progress reporting (percentage + ETA)
  - Pause / Resume support via threading.Event
  - Cancel support via flag
  - Speaker labels (SPEAKER_00, SPEAKER_01, ...) per segment
"""

import time
import logging
import threading
from pathlib import Path
from typing import Optional

from config import load_settings

logger = logging.getLogger(__name__)

# Global model cache so we don't reload on every request
_model = None
_model_name: Optional[str] = None

# ─── Transcription Job State ─────────────────────────────
# { meeting_id: { progress, eta_seconds, status, segments_done, ... } }
transcription_jobs: dict = {}
_job_locks: dict = {}  # per-job threading locks


def _get_job(meeting_id: int) -> dict:
    """Get or create a job state dict."""
    if meeting_id not in transcription_jobs:
        transcription_jobs[meeting_id] = {
            "progress": 0.0,          # 0-100
            "eta_seconds": -1,         # estimated seconds remaining (-1 = unknown)
            "status": "idle",          # idle | loading_model | transcribing | aligning | diarizing | paused | cancelled | completed | error
            "segments_done": 0,
            "current_time_sec": 0.0,   # current position in audio
            "total_duration_sec": 0.0,
            "elapsed_sec": 0.0,
            "pause_event": threading.Event(),
            "cancel_flag": False,
            "error": "",
        }
        transcription_jobs[meeting_id]["pause_event"].set()  # not paused by default
    return transcription_jobs[meeting_id]


def pause_job(meeting_id: int):
    """Pause a running transcription."""
    job = _get_job(meeting_id)
    if job["status"] in ("transcribing", "aligning", "diarizing"):
        job["pause_event"].clear()  # block the loop
        job["status"] = "paused"
        logger.info(f"Transcription paused for meeting {meeting_id}")


def resume_job(meeting_id: int):
    """Resume a paused transcription."""
    job = _get_job(meeting_id)
    if job["status"] == "paused":
        job["status"] = "transcribing"
        job["pause_event"].set()  # unblock the loop
        logger.info(f"Transcription resumed for meeting {meeting_id}")


def cancel_job(meeting_id: int):
    """Cancel a running/paused transcription."""
    job = _get_job(meeting_id)
    job["cancel_flag"] = True
    job["status"] = "cancelled"
    # Also unblock if paused, so the loop can exit
    job["pause_event"].set()
    logger.info(f"Transcription cancelled for meeting {meeting_id}")


def get_job_progress(meeting_id: int) -> dict:
    """Return current progress info (safe to call from any thread)."""
    job = _get_job(meeting_id)
    return {
        "progress": round(job["progress"], 1),
        "eta_seconds": round(job["eta_seconds"], 1) if job["eta_seconds"] >= 0 else -1,
        "status": job["status"],
        "segments_done": job["segments_done"],
        "current_time_sec": round(job["current_time_sec"], 1),
        "total_duration_sec": round(job["total_duration_sec"], 1),
        "elapsed_sec": round(job["elapsed_sec"], 1),
        "error": job["error"],
    }


def cleanup_job(meeting_id: int):
    """Remove job state after completion."""
    transcription_jobs.pop(meeting_id, None)


# ─── WhisperX Model ────────────────────────────────────────

def _get_device_and_compute():
    """Determine device + compute type based on settings and hardware."""
    settings = load_settings()
    device = settings.whisper_device

    if device == "auto":
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"

    compute_type = "float16" if device == "cuda" else "int8"
    return device, compute_type


def get_model():
    """Load or return cached WhisperX model."""
    global _model, _model_name
    import whisperx

    settings = load_settings()
    model_name = settings.whisper_model

    if _model is None or _model_name != model_name:
        device, compute_type = _get_device_and_compute()
        logger.info(f"Loading WhisperX model '{model_name}' on {device} ({compute_type})...")
        # initial_prompt guides Whisper to produce punctuation for CJK languages
        asr_options = {
            "initial_prompt": (
                "以下是一段會議錄音的逐字稿，請使用正確的標點符號。"
                "包含句號、逗號、問號、驚嘆號等標點符號。"
            ),
        }
        _model = whisperx.load_model(
            model_name, device, compute_type=compute_type,
            asr_options=asr_options,
        )
        _model_name = model_name
        logger.info("WhisperX model loaded.")

    return _model


def _get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds."""
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(audio_path)
        return len(audio) / 1000.0
    except Exception:
        return 0.0


# ─── Transcription with Diarization ──────────────────────

def transcribe(audio_path: str, language: Optional[str] = None, meeting_id: Optional[int] = None) -> dict:
    """
    Transcribe an audio file with WhisperX + speaker diarization.

    Args:
        audio_path: Path to wav/mp3/m4a/caf audio file.
        language: ISO language code (e.g. 'zh', 'en') or None for auto-detect.
        meeting_id: If provided, enables progress/pause/cancel tracking.

    Returns:
        {
            "text": full transcript string (with speaker labels),
            "segments": [ {start, end, text, speaker}, ... ],
            "language": detected language code,
            "duration": total audio duration in seconds,
            "speakers": list of unique speaker labels
        }

    Raises:
        InterruptedError: If the job was cancelled.
    """
    import whisperx

    job = _get_job(meeting_id) if meeting_id else None
    settings = load_settings()

    # Update status: loading model
    if job:
        job["status"] = "loading_model"
        job["progress"] = 0.0
        job["cancel_flag"] = False
        job["pause_event"].set()

    model = get_model()
    device, compute_type = _get_device_and_compute()

    lang = language
    if lang == "auto" or lang is None:
        lang = None  # WhisperX auto-detects when None

    logger.info(f"Transcribing with WhisperX: {audio_path} (language={lang or 'auto'})")

    # Get total duration for progress tracking
    total_duration = _get_audio_duration(audio_path)
    if job:
        job["total_duration_sec"] = total_duration
        job["status"] = "transcribing"

    start_time = time.time()

    # ── Check cancel ──
    if job and job["cancel_flag"]:
        raise InterruptedError("Transcription cancelled by user")

    # ── Step 1: Load audio ──
    audio = whisperx.load_audio(audio_path)

    # ── Step 2: Transcribe with WhisperX ──
    if job:
        job["pause_event"].wait()
        if job["cancel_flag"]:
            raise InterruptedError("Transcription cancelled by user")

    transcribe_kwargs = {"batch_size": 16}
    if lang:
        transcribe_kwargs["language"] = lang

    result = model.transcribe(audio, **transcribe_kwargs)
    detected_lang = result.get("language", lang or "unknown")

    if job:
        job["progress"] = 40.0
        job["elapsed_sec"] = time.time() - start_time
        elapsed = job["elapsed_sec"]
        # Estimate: transcription ~40%, alignment ~20%, diarization ~40%
        job["eta_seconds"] = elapsed * (60.0 / 40.0)

    logger.info(f"WhisperX transcription done, detected language: {detected_lang}")

    # ── Step 3: Alignment (word-level timestamps) ──
    if job:
        job["pause_event"].wait()
        if job["cancel_flag"]:
            raise InterruptedError("Transcription cancelled by user")
        job["status"] = "aligning"

    try:
        align_model, align_metadata = whisperx.load_align_model(
            language_code=detected_lang, device=device
        )
        result = whisperx.align(
            result["segments"], align_model, align_metadata, audio, device,
            return_char_alignments=False
        )
        logger.info("WhisperX alignment done.")
    except Exception as e:
        logger.warning(f"Alignment failed (non-critical, continuing without it): {e}")

    if job:
        job["progress"] = 60.0
        job["elapsed_sec"] = time.time() - start_time
        elapsed = job["elapsed_sec"]
        job["eta_seconds"] = elapsed * (40.0 / 60.0)

    # ── Step 4: Speaker Diarization ──
    diarize_success = False
    diarize_error = ""
    hf_token = getattr(settings, 'hf_token', '') or ''

    if hf_token:
        if job:
            job["pause_event"].wait()
            if job["cancel_flag"]:
                raise InterruptedError("Transcription cancelled by user")
            job["status"] = "diarizing"

        try:
            from whisperx.diarize import DiarizationPipeline
            logger.info(f"Loading pyannote diarization pipeline (token: {hf_token[:8]}...)")
            diarize_pipeline = DiarizationPipeline(
                token=hf_token, device=device
            )
            logger.info("Diarization pipeline loaded, running on audio...")
            diarize_segments = diarize_pipeline(audio_path)
            logger.info(f"Diarization segments obtained, assigning speakers to words...")
            result = whisperx.assign_word_speakers(diarize_segments, result)
            diarize_success = True
            logger.info("WhisperX speaker diarization done successfully.")
        except Exception as e:
            diarize_error = str(e)
            logger.error(f"Speaker diarization failed: {e}", exc_info=True)
    else:
        diarize_error = "未設定 HuggingFace Token，請至設定頁面填入 HuggingFace Token 以啟用說話者辨識。"
        logger.info("No HuggingFace token configured — skipping speaker diarization.")

    if job:
        job["progress"] = 90.0
        job["elapsed_sec"] = time.time() - start_time
        elapsed = job["elapsed_sec"]
        job["eta_seconds"] = elapsed * (10.0 / 90.0)

    # ── Step 5: Build output ──
    segments = []
    full_text_parts = []
    speakers_set = set()
    current_speaker = None

    for seg in result.get("segments", []):
        speaker = seg.get("speaker", "")
        text = seg.get("text", "").strip()
        seg_start = seg.get("start", 0)
        seg_end = seg.get("end", 0)

        if not text:
            continue

        if speaker:
            speakers_set.add(speaker)

        segments.append({
            "start": round(seg_start, 2),
            "end": round(seg_end, 2),
            "text": text,
            "speaker": speaker,
        })

        # Build readable transcript with speaker labels
        if diarize_success and speaker:
            if speaker != current_speaker:
                current_speaker = speaker
                full_text_parts.append(f"\n[{speaker}]")
            full_text_parts.append(text)
        else:
            full_text_parts.append(text)

        # Update progress
        if job and total_duration > 0:
            seg_progress = 90.0 + min((seg_end / total_duration) * 10.0, 9.9)
            job["progress"] = seg_progress
            job["segments_done"] = len(segments)
            job["current_time_sec"] = seg_end

    full_text = "\n".join(full_text_parts).strip()

    # ── Done ──
    if job:
        job["progress"] = 100.0
        job["eta_seconds"] = 0
        job["status"] = "completed"
        job["elapsed_sec"] = time.time() - start_time
        job["segments_done"] = len(segments)

    speakers_list = sorted(list(speakers_set))
    logger.info(
        f"Transcription done: {len(segments)} segments, language={detected_lang}, "
        f"duration={total_duration:.1f}s, speakers={len(speakers_list)}"
    )

    return {
        "text": full_text,
        "segments": segments,
        "language": detected_lang,
        "duration": round(total_duration, 2),
        "speakers": speakers_list,
        "diarize_error": diarize_error,
    }
