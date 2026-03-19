import asyncio
import logging

from openai import OpenAI

from app.config import settings
from app.services.retry import async_retry

logger = logging.getLogger(__name__)


def _transcribe(audio_path: str) -> str:
    """Call Whisper API to transcribe audio (blocking)."""
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    with open(audio_path, "rb") as f:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=f,
            response_format="text",
        )
    return response.strip()


@async_retry(max_attempts=3, base_delay=1.0)
async def _transcribe_with_retry(audio_path: str) -> str:
    return await asyncio.to_thread(_transcribe, audio_path)


async def transcribe_audio(audio_path: str) -> str:
    """Async wrapper: transcribe an audio file using OpenAI Whisper."""
    if not audio_path:
        logger.info("No audio file provided, skipping transcription")
        return ""

    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set, skipping transcription")
        return ""

    try:
        result = await _transcribe_with_retry(audio_path)
        logger.info("Transcription complete (%d chars)", len(result))
        return result
    except Exception:
        logger.exception("Transcription failed for %s", audio_path)
        return ""
