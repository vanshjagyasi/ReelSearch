import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import auth, entities, posts, search
from app.config import settings
from app.db.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting ReelSearch API...")
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("Database connection verified.")
    yield
    # Shutdown
    await engine.dispose()
    logger.info("ReelSearch API shut down.")


app = FastAPI(
    title="ReelSearch",
    description="AI-powered search engine for social media reels",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Auth"])
app.include_router(posts.router, prefix="/api", tags=["Reels"])
app.include_router(entities.router, prefix="/api", tags=["Entities"])
app.include_router(search.router, prefix="/api", tags=["Search"])


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
