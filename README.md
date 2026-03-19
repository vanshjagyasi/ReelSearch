# ReelSearch

AI-powered search engine for social media reels. Save reels from Instagram, YouTube, and TikTok — then search them with natural language.

## How It Works

1. **Save** — Paste a reel URL. The system fetches metadata, transcribes audio, and analyzes video frames.
2. **Understand** — AI extracts entities (products, brands, places, styles), tags, and relationships from the content.
3. **Build** — Entities are deduplicated and linked into a knowledge graph that grows smarter with every reel.
4. **Search** — Natural language queries are matched against the entity graph, tags, and semantic embeddings using hybrid search.

## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI (Python, async) |
| Database | PostgreSQL + pgvector + pg_trgm |
| ORM / Migrations | SQLAlchemy 2.0 (async) + Alembic |
| LLM Orchestration | LangChain + OpenAI GPT-4o |
| Transcription | OpenAI Whisper API |
| Vision | OpenAI GPT-4o Vision |
| Embeddings | OpenAI text-embedding-3-small |
| Video Download | yt-dlp + ffmpeg |
| Containerization | Docker + Docker Compose |

## Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) and Docker Compose
- An API key for [OpenAI](https://platform.openai.com/)

### Setup

```bash
# Clone the repo
git clone https://github.com/your-username/reelsearch.git
cd reelsearch

# Create your environment file
cp .env.example .env
# Edit .env and add your API keys

# Start everything
docker compose up --build
```

### Run Migrations

```bash
# In a separate terminal, run the database migrations
docker compose exec app alembic upgrade head
```

### Use the API

Open the interactive Swagger docs at **http://localhost:8000/docs**

Or use curl:

```bash
# Save a reel
curl -X POST http://localhost:8000/api/reels \
  -H "Content-Type: application/json" \
  -d '{"url": "https://instagram.com/reel/abc123"}'

# List all saved reels
curl http://localhost:8000/api/reels

# Get a specific reel
curl http://localhost:8000/api/reels/{id}

# Delete a reel
curl -X DELETE http://localhost:8000/api/reels/{id}

# Search reels
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "budget home decor ideas"}'

# Health check
curl http://localhost:8000/health
```

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/auth/register` | Create a new account |
| `POST` | `/api/auth/login` | Log in (returns access token) |
| `POST` | `/api/auth/refresh` | Refresh access token (uses cookie) |
| `POST` | `/api/auth/logout` | Log out (clears cookie) |
| `GET` | `/api/auth/me` | Get current user info |
| `POST` | `/api/reels` | Save a reel URL for processing |
| `GET` | `/api/reels` | List all saved reels |
| `GET` | `/api/reels/{id}` | Get full reel details |
| `DELETE` | `/api/reels/{id}` | Delete a saved reel |
| `GET` | `/api/reels/{id}/status` | Poll processing status |
| `GET` | `/api/stats` | Processing stats for current user |
| `GET` | `/api/entities` | List top entities by mention count |
| `GET` | `/api/entities/{id}` | Get entity details + linked reels |
| `GET` | `/api/entities/{id}/related` | Get related entities |
| `POST` | `/api/search` | Search reels with natural language |
| `GET` | `/health` | Health check |

## Project Structure

```
reelsearch/
├── docker-compose.yml          # Postgres + app services
├── Dockerfile                  # Python 3.12 + ffmpeg
├── requirements.txt            # Python dependencies
├── alembic.ini                 # Alembic migration config
├── .env.example                # Environment variable template
│
├── app/
│   ├── main.py                 # FastAPI app, lifespan, routers
│   ├── config.py               # Pydantic Settings (env vars)
│   │
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── post.py             # Post (saved reels)
│   │   ├── entity.py           # Entity (products, brands, etc.)
│   │   ├── post_entity.py      # Post ↔ Entity junction
│   │   └── entity_relation.py  # Entity ↔ Entity relationships
│   │
│   ├── schemas/                # Pydantic request/response models
│   │   ├── post.py             # SaveReelRequest, ReelResponse, etc.
│   │   ├── entity.py           # EntityResponse, EntityDetail
│   │   └── search.py           # SearchRequest, SearchResponse
│   │
│   ├── api/                    # Route handlers
│   │   ├── posts.py            # CRUD endpoints for reels
│   │   ├── entities.py         # Entity browsing endpoints
│   │   └── search.py           # Search endpoint
│   │
│   ├── services/               # Business logic
│   │   ├── ingest.py           # Orchestrates full enrichment pipeline
│   │   ├── metadata.py         # yt-dlp metadata + media download
│   │   ├── transcription.py    # OpenAI Whisper transcription
│   │   ├── vision.py           # GPT-4o Vision frame analysis
│   │   ├── extraction.py       # GPT-4o entity/tag extraction
│   │   ├── resolution.py       # 3-step entity deduplication cascade
│   │   ├── embedding.py        # OpenAI embedding generation
│   │   └── search.py           # Hybrid search engine with RRF
│   │
│   ├── prompts/                # LLM prompt templates
│   │
│   └── db/
│       ├── database.py         # Async SQLAlchemy engine + session
│       └── migrations/         # Alembic migrations
│
├── tests/                      # Test suite
└── scripts/                    # Utility scripts
```

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string (asyncpg) | Yes |
| `OPENAI_API_KEY` | OpenAI API key for GPT-4o, Whisper, and embeddings | Yes |
| `JWT_SECRET_KEY` | Secret key for signing JWT tokens | Yes |
| `CORS_ORIGINS` | Comma-separated allowed origins | No (default: http://localhost:3000) |
| `APP_ENV` | `development` or `production` | No (default: development) |
| `LOG_LEVEL` | Logging level | No (default: INFO) |

## Deploy to Railway

1. Push your code to a GitHub repo
2. Create a new project on [Railway](https://railway.app)
3. Add a **Postgres** plugin — copy the `DATABASE_URL` and change `postgresql://` to `postgresql+asyncpg://`
4. Add a **Backend** service — connect your GitHub repo, set root directory to `/`
5. Set backend environment variables:
   - `DATABASE_URL` — from step 3 (with `+asyncpg`)
   - `OPENAI_API_KEY` — your OpenAI key
   - `JWT_SECRET_KEY` — a random secret (e.g. `openssl rand -hex 32`)
   - `CORS_ORIGINS` — your frontend's Railway public URL
6. Add a **Frontend** service — same repo, set root directory to `frontend/`
7. Set frontend environment variables:
   - `API_UPSTREAM` — backend's internal Railway URL (e.g. `http://backend.railway.internal:PORT`)
8. Assign public domains to both services
9. Backend auto-runs migrations on startup

## Development

```bash
# Rebuild after changing requirements.txt
docker compose up --build

# View logs
docker compose logs -f app

# Run migrations
docker compose exec app alembic upgrade head

# Create a new migration after model changes
docker compose exec app alembic revision --autogenerate -m "description"

# Stop everything
docker compose down

# Stop and remove volumes (wipes DB)
docker compose down -v
```
