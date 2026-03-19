"""Embedding generation service.

Combines AI summary, entity names, and tags into a single text string,
then generates a 1536-dimensional vector via OpenAI text-embedding-3-small.
"""

import asyncio
import logging

from openai import OpenAI

from app.config import settings
from app.services.retry import async_retry

logger = logging.getLogger(__name__)


def build_embedding_text(
    summary: str,
    entity_names: list[str],
    tags: list[str],
) -> str:
    """Combine enriched content into a single string for embedding."""
    parts = [summary or ""]
    if entity_names:
        parts.append("Entities: " + ", ".join(entity_names))
    if tags:
        parts.append("Tags: " + ", ".join(tags))
    return " | ".join(p for p in parts if p)


def _generate(text: str) -> list[float]:
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text,
    )
    return response.data[0].embedding


async def generate_embedding(text: str) -> list[float] | None:
    """Generate a 1536-dim embedding for the given text.

    Returns None if the API key is not set or the call fails.
    """
    if not text.strip():
        return None
    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set, skipping embedding generation")
        return None
    @async_retry(max_attempts=3, base_delay=1.0)
    async def _generate_with_retry():
        return await asyncio.to_thread(_generate, text)

    try:
        result = await _generate_with_retry()
        logger.info("Embedding generated (%d dimensions)", len(result))
        return result
    except Exception:
        logger.exception("Embedding generation failed")
        return None
