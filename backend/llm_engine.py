"""LLM-based meeting summary engine.

Supports three providers: OpenAI (ChatGPT), Anthropic (Claude), Google (Gemini).
The user picks their preferred provider in the app settings.
"""

import json
import logging
from typing import Optional
from config import load_settings

logger = logging.getLogger(__name__)

# ----- Prompt Template -----

SUMMARY_SYSTEM_PROMPT = """你是一位專業的會議記錄助理。請根據以下逐字稿產生結構化的會議摘要。

請以 JSON 格式回傳，包含以下欄位：
{
  "title": "會議主旨（簡短標題）",
  "date": "會議日期（如果逐字稿中有提及，否則留空）",
  "participants": "參與者列表（如果逐字稿中有提及，以逗號分隔，否則留空）",
  "brief_summary": "200字以內的會議摘要描述",
  "detailed_summary": "詳細的會議摘要，包含所有重要討論內容，使用 Markdown 格式",
  "action_items": "待辦事項清單，每項一行，使用 - 開頭"
}

規則：
1. brief_summary 必須在200字（中文字）以內
2. detailed_summary 要全面但精煉，使用 Markdown 標題和列表來組織
3. action_items 每個項目要明確，包含負責人（如果有提及）
4. 如果逐字稿語言是中文，請用繁體中文回覆；如果是英文，用英文回覆
5. 只回傳 JSON，不要加任何其他文字
"""


def _build_user_message(transcript: str, language: str = "") -> str:
    lang_hint = f"\n\n（音檔偵測語言：{language}）" if language else ""
    return f"以下是會議逐字稿：\n\n{transcript}{lang_hint}"


# ----- Provider Implementations -----

def _summarize_openai(transcript: str, language: str) -> dict:
    """Summarize using OpenAI ChatGPT."""
    from openai import OpenAI
    settings = load_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    response = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(transcript, language)},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


def _summarize_anthropic(transcript: str, language: str) -> dict:
    """Summarize using Anthropic Claude."""
    import anthropic
    settings = load_settings()
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        system=SUMMARY_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": _build_user_message(transcript, language)},
        ],
        temperature=0.3,
    )
    text = response.content[0].text
    # Claude may wrap JSON in markdown code fences
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return json.loads(text.strip())


def _summarize_gemini(transcript: str, language: str) -> dict:
    """Summarize using Google Gemini."""
    import google.generativeai as genai
    settings = load_settings()
    genai.configure(api_key=settings.gemini_api_key)

    model = genai.GenerativeModel(settings.gemini_model)
    prompt = SUMMARY_SYSTEM_PROMPT + "\n\n" + _build_user_message(transcript, language)

    response = model.generate_content(
        prompt,
        generation_config=genai.types.GenerationConfig(
            temperature=0.3,
            response_mime_type="application/json",
        ),
    )
    text = response.text
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0]
    elif "```" in text:
        text = text.split("```")[1].split("```")[0]
    return json.loads(text.strip())


# ----- Public API -----

PROVIDERS = {
    "openai": _summarize_openai,
    "anthropic": _summarize_anthropic,
    "gemini": _summarize_gemini,
}


def summarize_transcript(
    transcript: str,
    language: str = "",
    provider: Optional[str] = None,
) -> dict:
    """
    Generate a structured meeting summary from a transcript.

    Args:
        transcript: Full transcript text.
        language: Detected language code.
        provider: LLM provider name (openai/anthropic/gemini). Uses settings default if None.

    Returns:
        Dict with keys: title, date, participants, brief_summary, detailed_summary, action_items
    """
    settings = load_settings()
    provider = provider or settings.llm_provider

    if provider not in PROVIDERS:
        raise ValueError(f"Unknown LLM provider: {provider}. Choose from: {list(PROVIDERS.keys())}")

    logger.info(f"Generating summary with {provider}...")
    result = PROVIDERS[provider](transcript, language)
    logger.info(f"Summary generated: title='{result.get('title', '')}'")
    return result
