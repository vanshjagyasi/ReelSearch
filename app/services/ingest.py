import logging
import shutil
import tempfile
import time
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session_maker
from app.models.post import Post
from app.services.embedding import build_embedding_text, generate_embedding
from app.services.extraction import extract_entities
from app.services.metadata import download_media, download_thumbnail_b64, fetch_metadata
from app.services.resolution import resolve_and_persist_entities
from app.services.transcription import transcribe_audio
from app.services.vision import describe_frames

logger = logging.getLogger(__name__)


async def _update_post(session: AsyncSession, post_id: uuid.UUID, **kwargs) -> None:
    """Update a post row with the given fields."""
    result = await session.execute(select(Post).where(Post.id == post_id))
    post = result.scalar_one()
    for key, value in kwargs.items():
        setattr(post, key, value)
    await session.commit()


async def ingest_reel(post_id: uuid.UUID) -> None:
    """Full enrichment pipeline: metadata -> transcription -> vision.

    Runs as a background task. Uses its own DB session so the request
    handler's session is not held open.
    """
    start = time.time()
    logger.info("Starting ingestion for post %s", post_id)

    async with async_session_maker() as session:
        # Load the post
        result = await session.execute(select(Post).where(Post.id == post_id))
        post = result.scalar_one_or_none()
        if not post:
            logger.error("Post %s not found, aborting ingestion", post_id)
            return

        url = post.url
        user_id = post.user_id

        # Mark as processing
        post.status = "processing"
        await session.commit()

    work_dir = tempfile.mkdtemp(prefix="reelsearch_")

    try:
        # --- Step 1: Fetch metadata ---
        step_start = time.time()
        logger.info("[%s] Fetching metadata...", post_id)
        info = await fetch_metadata(url)
        logger.info("[%s] Metadata fetched in %.1fs", post_id, time.time() - step_start)

        # For Instagram, download and compress thumbnail before CDN URL expires
        metadata = info.get("metadata") or {}
        if info.get("platform") == "instagram" and metadata.get("thumbnail"):
            thumb_b64 = await download_thumbnail_b64(metadata["thumbnail"])
            if thumb_b64:
                metadata["thumbnail"] = thumb_b64
                logger.info("[%s] Instagram thumbnail saved as base64", post_id)

        async with async_session_maker() as session:
            await _update_post(
                session, post_id,
                caption=info.get("caption"),
                creator=info.get("creator"),
                platform=info.get("platform"),
                metadata_=metadata,
            )

        # --- Step 2: Download audio + video, extract frames ---
        step_start = time.time()
        logger.info("[%s] Downloading media...", post_id)
        media = await download_media(url, work_dir)
        logger.info("[%s] Media downloaded in %.1fs", post_id, time.time() - step_start)

        # --- Step 3: Transcribe audio ---
        step_start = time.time()
        logger.info("[%s] Transcribing audio...", post_id)
        transcript = await transcribe_audio(media["audio_path"])
        logger.info("[%s] Transcription done in %.1fs", post_id, time.time() - step_start)

        async with async_session_maker() as session:
            await _update_post(session, post_id, transcript=transcript)

        # --- Step 4: Describe frames (Vision) ---
        step_start = time.time()
        logger.info("[%s] Analyzing frames...", post_id)
        frame_description = await describe_frames(media["frame_paths"])
        logger.info("[%s] Vision analysis done in %.1fs", post_id, time.time() - step_start)

        async with async_session_maker() as session:
            await _update_post(session, post_id, frame_description=frame_description)

        # --- Step 5: Entity extraction ---
        step_start = time.time()
        logger.info("[%s] Extracting entities...", post_id)
        caption = info.get("caption", "")
        extraction = await extract_entities(caption, transcript, frame_description)
        logger.info("[%s] Extraction done in %.1fs", post_id, time.time() - step_start)

        async with async_session_maker() as session:
            await _update_post(
                session, post_id,
                ai_summary=extraction.get("summary"),
                ai_tags=extraction.get("tags") or None,
                content_type=extraction.get("content_type"),
                mood=extraction.get("mood"),
            )

        # --- Step 6: Entity resolution + persistence ---
        step_start = time.time()
        logger.info("[%s] Resolving entities...", post_id)
        entities = extraction.get("entities", [])
        relationships = extraction.get("relationships", [])
        async with async_session_maker() as session:
            entity_ids = await resolve_and_persist_entities(
                session, post_id, entities, relationships, user_id,
            )
        logger.info(
            "[%s] Resolved %d entities in %.1fs",
            post_id, len(entity_ids), time.time() - step_start,
        )

        # --- Step 7: Generate embedding ---
        step_start = time.time()
        logger.info("[%s] Generating embedding...", post_id)
        entity_names = [e.get("name", "") for e in entities if e.get("name")]
        tags = extraction.get("tags", []) or []
        summary = extraction.get("summary", "")
        embed_text = build_embedding_text(summary, entity_names, tags)
        embedding = await generate_embedding(embed_text)
        logger.info("[%s] Embedding done in %.1fs", post_id, time.time() - step_start)

        # Mark as ready (final step)
        async with async_session_maker() as session:
            await _update_post(session, post_id, embedding=embedding, status="ready")

        elapsed = time.time() - start
        logger.info("[%s] Ingestion complete in %.1fs", post_id, elapsed)

    except Exception:
        logger.exception("[%s] Ingestion failed", post_id)
        try:
            async with async_session_maker() as session:
                await _update_post(session, post_id, status="failed")
        except Exception:
            logger.exception("[%s] Failed to update status to 'failed'", post_id)

    finally:
        # Clean up temp files
        shutil.rmtree(work_dir, ignore_errors=True)
