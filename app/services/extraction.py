import logging

from langchain_openai import ChatOpenAI
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.config import settings
from app.prompts.extraction import EXTRACTION_SYSTEM_PROMPT, EXTRACTION_USER_PROMPT
from app.services.retry import async_retry

logger = logging.getLogger(__name__)


def _build_chain():
    """Build the LangChain extraction chain."""
    llm = ChatOpenAI(
        model="gpt-4o",
        temperature=0,
        api_key=settings.OPENAI_API_KEY,
        max_tokens=2000,
    )
    prompt = ChatPromptTemplate.from_messages([
        ("system", EXTRACTION_SYSTEM_PROMPT),
        ("human", EXTRACTION_USER_PROMPT),
    ])
    return prompt | llm | JsonOutputParser()


async def extract_entities(
    caption: str | None,
    transcript: str | None,
    frame_description: str | None,
) -> dict:
    """Extract entities, tags, relationships, and metadata from reel content.

    Returns a dict with keys: entities, relationships, tags, content_type, mood, summary.
    Returns empty/default structure on failure.
    """
    if not settings.OPENAI_API_KEY:
        logger.warning("OPENAI_API_KEY not set, skipping extraction")
        return _empty_result()

    chain = _build_chain()

    @async_retry(max_attempts=3, base_delay=1.0)
    async def _invoke():
        return await chain.ainvoke({
            "caption": caption or "(no caption)",
            "transcript": transcript or "(no speech detected)",
            "frame_description": frame_description or "(no visual description)",
        })

    try:
        result = await _invoke()
        # Validate expected keys exist
        result.setdefault("entities", [])
        result.setdefault("relationships", [])
        result.setdefault("tags", [])
        result.setdefault("content_type", "other")
        result.setdefault("mood", "")
        result.setdefault("summary", "")

        logger.info(
            "Extraction complete: %d entities, %d relationships, %d tags",
            len(result["entities"]),
            len(result["relationships"]),
            len(result["tags"]),
        )
        return result

    except Exception:
        logger.exception("Entity extraction failed")
        return _empty_result()


def _empty_result() -> dict:
    return {
        "entities": [],
        "relationships": [],
        "tags": [],
        "content_type": "other",
        "mood": "",
        "summary": "",
    }
