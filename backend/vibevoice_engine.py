"""Offline speech-to-text using Microsoft VibeVoice-ASR.

VibeVoice-ASR provides:
  - 60-minute long-form audio in a single pass
  - Unified ASR + Speaker Diarization + Timestamps (Who / When / What)
  - Natively multilingual (50+ languages), no language setting needed
  - Based on Qwen2.5-7B backbone

References:
  https://github.com/microsoft/VibeVoice
  https://huggingface.co/microsoft/VibeVoice-ASR
"""

import time
import logging
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# ─── 模型快取 ─────────────────────────────────────────────────
_model = None
_processor = None
_model_id: Optional[str] = None

# ─── 轉錄工作狀態 ──────────────────────────────────────────────
# { meeting_id: { progress, eta_seconds, status, ... } }
transcription_jobs: dict = {}


def _get_job(meeting_id: int) -> dict:
    if meeting_id not in transcription_jobs:
        transcription_jobs[meeting_id] = {
            "progress": 0.0,
            "eta_seconds": -1,
            "status": "idle",
            "segments_done": 0,
            "current_time_sec": 0.0,
            "total_duration_sec": 0.0,
            "elapsed_sec": 0.0,
            "pause_event": threading.Event(),
            "cancel_flag": False,
            "error": "",
        }
        transcription_jobs[meeting_id]["pause_event"].set()
    return transcription_jobs[meeting_id]


def pause_job(meeting_id: int):
    job = _get_job(meeting_id)
    if job["status"] in ("transcribing", "loading_model"):
        job["pause_event"].clear()
        job["status"] = "paused"
        logger.info(f"Transcription paused for meeting {meeting_id}")


def resume_job(meeting_id: int):
    job = _get_job(meeting_id)
    if job["status"] == "paused":
        job["status"] = "transcribing"
        job["pause_event"].set()
        logger.info(f"Transcription resumed for meeting {meeting_id}")


def cancel_job(meeting_id: int):
    job = _get_job(meeting_id)
    job["cancel_flag"] = True
    job["status"] = "cancelled"
    job["pause_event"].set()
    logger.info(f"Transcription cancelled for meeting {meeting_id}")


def get_job_progress(meeting_id: int) -> dict:
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
    transcription_jobs.pop(meeting_id, None)


# ─── 裝置偵測 ──────────────────────────────────────────────────

def _get_device_and_dtype():
    """
    回傳 (device_str, torch_dtype, attn_implementation)。
    優先順序：CUDA > MPS (Apple Silicon) > CPU。
    """
    import torch

    if torch.cuda.is_available():
        return "cuda", torch.bfloat16, "sdpa"

    # Apple Silicon — MPS
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps", torch.float32, "sdpa"

    return "cpu", torch.float32, "sdpa"


# ─── 模型載入 ──────────────────────────────────────────────────

def get_model():
    """載入或取得快取的 VibeVoice-ASR 模型與 Processor。"""
    global _model, _processor, _model_id

    from config import load_settings
    settings = load_settings()
    model_id = getattr(settings, "vibevoice_model", "microsoft/VibeVoice-ASR")

    if _model is not None and _model_id == model_id:
        return _model, _processor

    device, dtype, attn_impl = _get_device_and_dtype()
    logger.info(
        f"Loading VibeVoice-ASR model '{model_id}' on {device} "
        f"(dtype={dtype}, attn={attn_impl})..."
    )

    try:
        from vibevoice.modular.modeling_vibevoice_asr import (
            VibeVoiceASRForConditionalGeneration,
        )
        from vibevoice.processor.vibevoice_asr_processor import VibeVoiceASRProcessor
    except ImportError as e:
        raise ImportError(
            "VibeVoice 套件未安裝。請執行：\n"
            "  pip install git+https://github.com/microsoft/VibeVoice.git"
        ) from e

    _processor = VibeVoiceASRProcessor.from_pretrained(
        model_id,
        language_model_pretrained_name="Qwen/Qwen2.5-7B",
    )

    _model = VibeVoiceASRForConditionalGeneration.from_pretrained(
        model_id,
        dtype=dtype,
        attn_implementation=attn_impl,
        trust_remote_code=True,
    )
    _model = _model.to(device)
    _model.eval()
    _model_id = model_id

    logger.info("VibeVoice-ASR model loaded successfully.")
    return _model, _processor


def _get_audio_duration(audio_path: str) -> float:
    try:
        from pydub import AudioSegment
        audio = AudioSegment.from_file(audio_path)
        return len(audio) / 1000.0
    except Exception:
        return 0.0


# ─── 主轉錄函式 ────────────────────────────────────────────────

def transcribe(
    audio_path: str,
    language: Optional[str] = None,
    meeting_id: Optional[int] = None,
    hotwords: Optional[str] = None,
) -> dict:
    """
    使用 VibeVoice-ASR 轉錄音檔，同時輸出說話者辨識與時間戳。

    Args:
        audio_path:  音檔路徑（wav/mp3/m4a/caf 等）
        language:    語言代碼（VibeVoice 自動偵測，此參數保留相容性）
        meeting_id:  用於進度/暫停/取消追蹤
        hotwords:    自訂詞彙（會議術語、人名等），以逗號分隔

    Returns:
        {
            "text":     完整逐字稿（含說話者標籤）
            "segments": [ {start, end, text, speaker}, ... ]
            "language": 偵測到的語言代碼
            "duration": 音訊總長度（秒）
            "speakers": 說話者標籤列表
        }

    Raises:
        InterruptedError: 工作被取消時
    """
    import torch

    job = _get_job(meeting_id) if meeting_id else None
    device, dtype, _ = _get_device_and_dtype()

    if job:
        job["status"] = "loading_model"
        job["progress"] = 0.0
        job["cancel_flag"] = False
        job["pause_event"].set()

    model, processor = get_model()

    if job:
        job["pause_event"].wait()
        if job["cancel_flag"]:
            raise InterruptedError("Transcription cancelled by user")

    total_duration = _get_audio_duration(audio_path)
    if job:
        job["total_duration_sec"] = total_duration
        job["status"] = "transcribing"
        job["progress"] = 5.0

    logger.info(
        f"Transcribing with VibeVoice-ASR: {audio_path} "
        f"(duration={total_duration:.1f}s, device={device})"
    )

    start_time = time.time()

    # ── 準備 Processor 輸入 ──────────────────────────────────────
    # VibeVoice 接受音檔路徑的 list
    proc_kwargs = dict(
        audio=[audio_path],
        sampling_rate=None,
        return_tensors="pt",
        padding=True,
        add_generation_prompt=True,
    )

    # hotwords 注入（若 Processor 支援）
    if hotwords:
        proc_kwargs["context"] = hotwords

    inputs = processor(**proc_kwargs)
    inputs = {
        k: v.to(device) if isinstance(v, torch.Tensor) else v
        for k, v in inputs.items()
    }

    if job:
        job["progress"] = 15.0
        job["elapsed_sec"] = time.time() - start_time

    # ── 推論 ─────────────────────────────────────────────────────
    # max_new_tokens: 1 分鐘音訊約需 500 tokens；60 分鐘 = 32768
    max_new_tokens = min(32768, max(512, int(total_duration * 9)))

    if job:
        job["pause_event"].wait()
        if job["cancel_flag"]:
            raise InterruptedError("Transcription cancelled by user")

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            do_sample=False,          # greedy decoding（確定性輸出）
            pad_token_id=processor.pad_id,
            eos_token_id=processor.tokenizer.eos_token_id,
        )

    if job:
        job["progress"] = 85.0
        elapsed = time.time() - start_time
        job["elapsed_sec"] = elapsed

    # ── 解碼輸出 ─────────────────────────────────────────────────
    input_length = inputs["input_ids"].shape[1]
    generated_ids = output_ids[0, input_length:]

    # 去掉尾端 EOS padding
    eos_positions = (
        generated_ids == processor.tokenizer.eos_token_id
    ).nonzero(as_tuple=True)[0]
    if len(eos_positions) > 0:
        generated_ids = generated_ids[: eos_positions[0] + 1]

    raw_text = processor.decode(generated_ids, skip_special_tokens=True)

    # ── 解析結構化輸出（Who / When / What）────────────────────────
    try:
        parsed_segments = processor.post_process_transcription(raw_text)
    except Exception as e:
        logger.warning(f"post_process_transcription failed: {e}; falling back to raw text")
        parsed_segments = []

    # ── 組建統一輸出格式 ──────────────────────────────────────────
    segments = []
    full_text_parts = []
    speakers_set = set()
    current_speaker = None

    for seg in parsed_segments:
        speaker = seg.get("speaker_id", "")
        text = seg.get("text", "").strip()
        seg_start = _parse_time(seg.get("start_time", ""))
        seg_end = _parse_time(seg.get("end_time", ""))

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

        if speaker:
            if speaker != current_speaker:
                current_speaker = speaker
                full_text_parts.append(f"\n[{speaker}]")
            full_text_parts.append(text)
        else:
            full_text_parts.append(text)

    # 若解析失敗，退回整段 raw_text
    if not segments and raw_text.strip():
        full_text_parts = [raw_text.strip()]

    full_text = "\n".join(full_text_parts).strip()

    # 嘗試從第一個 segment 偵測語言（VibeVoice 不明確輸出語言代碼）
    detected_lang = _detect_language(full_text)

    if job:
        job["progress"] = 100.0
        job["eta_seconds"] = 0
        job["status"] = "completed"
        job["elapsed_sec"] = time.time() - start_time
        job["segments_done"] = len(segments)

    speakers_list = sorted(list(speakers_set))
    logger.info(
        f"VibeVoice-ASR done: {len(segments)} segments, "
        f"language≈{detected_lang}, duration={total_duration:.1f}s, "
        f"speakers={speakers_list}"
    )

    return {
        "text": full_text,
        "segments": segments,
        "language": detected_lang,
        "duration": round(total_duration, 2),
        "speakers": speakers_list,
        "diarize_error": "",   # VibeVoice 內建說話者辨識，無需外部 token
    }


# ─── 工具函式 ──────────────────────────────────────────────────

def _parse_time(time_str) -> float:
    """將 'HH:MM:SS.mmm' 或 '秒數' 字串轉為浮點秒數。"""
    if time_str is None:
        return 0.0
    if isinstance(time_str, (int, float)):
        return float(time_str)
    time_str = str(time_str).strip()
    try:
        return float(time_str)
    except ValueError:
        pass
    # 嘗試 HH:MM:SS.mmm
    try:
        parts = time_str.replace(",", ".").split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        elif len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
    except Exception:
        pass
    return 0.0


def _detect_language(text: str) -> str:
    """從文字內容簡單猜測語言（不依賴外部套件）。"""
    if not text:
        return "unknown"
    # 判斷 CJK 比例
    cjk = sum(1 for c in text if "\u4e00" <= c <= "\u9fff" or "\u3040" <= c <= "\u30ff")
    if cjk / max(len(text), 1) > 0.2:
        # 日文假名？
        kana = sum(1 for c in text if "\u3040" <= c <= "\u30ff")
        return "ja" if kana / max(len(text), 1) > 0.1 else "zh"
    return "en"
