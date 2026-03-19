import asyncio
import base64
import logging

from openai import OpenAI

from app.config import settings
from app.services.retry import async_retry

logger = logging.getLogger(__name__)

VISION_PROMPT = """Look at these frames from a social media reel. Provide:

1. VISUAL DESCRIPTION: What is happening visually? Describe the setting, \
objects, people, style, aesthetic, and any products or items visible.

2. ON-SCREEN TEXT: Transcribe ANY text visible in the frames exactly as shown. \
This includes: captions, subtitles, product names, recipe steps, \
quotes, labels, watermarks, usernames.

Be specific about products, brands, styles, and items you can identify."""


def _describe(frame_paths: list[str]) -> str:
    """Call OpenAI Vision API to describe frames (blocking)."""
    client = OpenAI(api_key=settings.OPENAI_API_KEY)

    content = []
    for path in frame_paths:
        with open(path, "rb") as f:
            img_data = base64.standard_b64encode(f.read()).decode("utf-8")
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img_data}",
            },
        })

    content.append({"type": "text", "text": VISION_PROMPT})

    response = client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1000,
        messages=[{"role": "user", "content": content}],
    )
    return response.choices[0].message.content


@async_retry(max_attempts=3, base_delay=1.0)
async def _describe_with_retry(frame_paths: list[str]) -> str:
    return await asyncio.to_thread(_describe, frame_paths)


async def describe_frames(frame_paths: list[str]) -> str:
    """Async wrapper: describe video frames using OpenAI Vision."""
    if not frame_paths:
        logger.info("No frames provided, skipping vision analysis")
        return ""

    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set, skipping vision analysis")
        return ""

    try:
        result = await _describe_with_retry(frame_paths)
        logger.info("Vision analysis complete (%d chars)", len(result))
        return result
    except Exception:
        logger.exception("Vision analysis failed")
        return ""
