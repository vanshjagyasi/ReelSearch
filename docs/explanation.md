# ReelSearch — Detailed Technical Explanation

This document explains the architecture, design decisions, and how every part of ReelSearch works. It is intended for developers joining the project or anyone who wants to understand the system deeply.

---

## Table of Contents

1. [The Problem](#the-problem)
2. [The Solution](#the-solution)
3. [Architecture Overview](#architecture-overview)
4. [Authentication & Per-User Isolation](#authentication--per-user-isolation)
5. [Database Design](#database-design)
6. [The Enrichment Pipeline](#the-enrichment-pipeline)
7. [Entity Extraction — The Core IP](#entity-extraction--the-core-ip)
8. [Entity Resolution — Deduplication Cascade](#entity-resolution--deduplication-cascade)
9. [The Knowledge Graph](#the-knowledge-graph)
10. [Hybrid Search Engine](#hybrid-search-engine)
11. [Frontend](#frontend)
12. [Production Hardening & Deployment](#production-hardening--deployment)
13. [Tech Stack Rationale](#tech-stack-rationale)
14. [Project Structure](#project-structure)
15. [Build Phases](#build-phases)

---

## The Problem

People save hundreds of reels across Instagram, YouTube, and TikTok. These reels contain valuable information — product recommendations, recipes, travel tips, workout routines, style inspiration — but there's no way to find them later.

Social media platforms offer no search within saved content. Users are left scrolling through hundreds of saved reels trying to remember "which reel had that shelf" or "who recommended that restaurant."

The core challenge is that reel content is **multimodal** (audio + video + text overlays + captions) and **unstructured**. A traditional keyword search won't work because the information is locked inside audio and video, not text.

---

## The Solution

ReelSearch is a personal search engine for saved reels. The key insight is that instead of treating reels as opaque blobs, we **deeply understand their content** and build a **structured knowledge graph** across all saved reels.

The system:

1. **Extracts content** from every modality: captions (text), audio (via transcription), video frames (via vision AI), and text overlays (via OCR)
2. **Identifies specific entities** — not just generic tags like "furniture" but specific things like "IKEA KALLAX Shelf" with attributes like price, color, and dimensions
3. **Resolves entities across reels** — recognizing that "KALLAX shelf," "that IKEA shelf," and "KALLAX bookshelf" are all the same entity
4. **Builds relationships** between entities — "KALLAX Shelf" is made_by "IKEA," pairs_with "SKÅDIS Pegboard," and fits_style "Scandinavian Minimalist"
5. **Enables natural language search** — queries like "budget Scandinavian bedroom ideas" traverse the entity graph, match tags, and fall back to semantic similarity

The more reels a user saves, the smarter the system gets. Each reel enriches existing entities with new context and relationships.

---

## Architecture Overview

```
User                    FastAPI                     Services
  |                       |                            |
  |-- POST /api/reels --> |                            |
  |<-- {id, pending} ---- |                            |
  |                       |--- Background Task ------> |
  |                       |                            |
  |                       |    1. Fetch metadata       | (yt-dlp)
  |                       |    2. Download audio       | (yt-dlp + ffmpeg)
  |                       |    3. Extract frames       | (ffmpeg)
  |                       |    4. Transcribe audio     | (Whisper API)
  |                       |    5. Describe frames      | (GPT-4o Vision)
  |                       |    6. Extract entities     | (GPT-4o + LangChain)
  |                       |    7. Resolve entities     | (pg_trgm + GPT-4o)
  |                       |    8. Generate embedding   | (OpenAI Embeddings)
  |                       |                            |
  |                       |<-- status: ready --------- |
  |                       |                            |
  |-- POST /api/search -> |                            |
  |                       |    1. Decompose query      | (GPT-4o)
  |                       |    2. Entity graph search  | (Postgres)
  |                       |    3. Tag matching         | (Postgres GIN)
  |                       |    4. Vector similarity    | (pgvector)
  |                       |    5. Merge via RRF        |
  |<-- ranked results --- |                            |
```

The architecture is intentionally simple: **one Python process, one Postgres database, one React frontend.** There are no message queues, caches, or microservices. Background processing uses Python's `asyncio.create_task()` — good enough for a personal tool.

All AI-heavy work happens in the background pipeline. The API responses are fast because saving a reel returns immediately with `status: pending`, and the enrichment runs asynchronously.

All API endpoints (except `/health` and thumbnails) require authentication via JWT tokens. Each user has their own isolated collection of reels and entities.

---

## Authentication & Per-User Isolation

ReelSearch uses username/password authentication with JWT tokens.

### Auth Flow

1. **Registration** — `POST /api/auth/register` with username + password. Password is hashed with `bcrypt` and stored. Returns an access token (30min) and sets an HttpOnly refresh token cookie (7 days).
2. **Login** — `POST /api/auth/login` validates credentials and returns the same token pair.
3. **Access** — Every API request includes `Authorization: Bearer <access_token>`. The `get_current_user` dependency decodes the JWT, loads the user from the database, and injects it into route handlers.
4. **Token Refresh** — When the access token expires, the frontend calls `POST /api/auth/refresh` which reads the HttpOnly cookie and returns a new access token. This happens transparently — the user stays logged in.
5. **Logout** — `POST /api/auth/logout` clears the refresh cookie.

### Implementation Details

- **Password hashing**: Uses the `bcrypt` library directly (`bcrypt.hashpw()` / `bcrypt.checkpw()`). No wrapper libraries — bcrypt is battle-tested and maintained.
- **JWT tokens**: `python-jose` with HS256 signing. The `JWT_SECRET_KEY` is loaded from environment variables.
- **Auth dependency**: `app/api/deps.py` defines `get_current_user()` using FastAPI's `OAuth2PasswordBearer`. Every protected route adds `current_user: User = Depends(get_current_user)`.
- **Username normalization**: Usernames are lowercased and stripped on registration and login. Only alphanumeric characters, hyphens, and underscores are allowed (min 3 chars).

### Per-User Data Isolation

Every `posts` and `entities` row has a `user_id` FK pointing to `users.id`. This is enforced at every level:

- **Saving reels**: `post.user_id = current_user.id` on creation. Duplicate check is `WHERE url = :url AND user_id = :user_id` — different users can save the same reel URL.
- **Listing/viewing reels**: All queries filter by `WHERE user_id = current_user.id`.
- **Entity resolution**: Entities are scoped per user. User A's "IKEA KALLAX Shelf" entity is separate from User B's.
- **Search**: All three search tiers (entity graph, tags, vector) filter by `user_id`.
- **Thumbnails**: Served publicly without auth (they're just images, no sensitive data).

### Database Migration

The `002_add_auth` migration handles the transition:
1. Creates the `users` table with a unique index on `username`
2. Inserts a system user (`00000000-...`) for existing data
3. Adds `user_id` to `posts` and `entities`, backfills with the system user, then sets NOT NULL
4. Changes the URL uniqueness constraint from `UNIQUE(url)` to `UNIQUE(url, user_id)`

---

## Database Design

The database has five tables — a users table and four tables that form a per-user knowledge graph:

### `users` — User Accounts

Stores authentication credentials and profile info. Each user has an isolated set of reels and entities.

Key columns:
- `username` — Unique, lowercase, indexed with a unique constraint
- `hashed_password` — bcrypt hash
- `display_name` — Optional display name
- `is_active` — For soft-disable (default true)

### `posts` — The Saved Reels

Stores everything about a reel: the original URL, raw extracted content (caption, transcript, frame description), AI-generated analysis (summary, tags, content type, mood), the vector embedding for semantic search, and processing status.

Key columns:
- `user_id` — FK to `users.id`, scopes all queries to the owning user
- `transcript` — Full audio transcription from Whisper
- `frame_description` — Visual description + OCR from GPT-4o Vision
- `ai_summary` — LLM-generated 2-3 sentence summary
- `ai_tags` — Array of descriptive tags (stored as Postgres ARRAY for GIN indexing)
- `embedding` — 1536-dimensional vector from OpenAI (stored via pgvector)
- `status` — Tracks processing: `pending` → `processing` → `ready` (or `failed`)
- `metadata` — JSONB for flexible platform-specific data (likes, duration, thumbnail URL)

URL uniqueness is enforced per user: `UNIQUE(url, user_id)` — different users can save the same reel.

### `entities` — The Directory of Things

Every real-world thing mentioned in a user's reels gets one row here. Entities are scoped per user (`user_id` FK) so each user has their own entity graph. Entities have a `type` (product, brand, place, book, person, style, recipe, exercise, technique) and flexible `attributes` stored as JSONB.

Key columns:
- `normalized_name` — Lowercase, stripped version of the name for matching
- `attributes` — Flexible JSONB: `{brand: "IKEA", price: "$79", color: "white"}` for products, `{cuisine: "Italian", difficulty: "easy"}` for recipes, etc.
- `mention_count` — How many reels reference this entity (used for ranking)

The `normalized_name` column has a **trigram GIN index** (`pg_trgm`) enabling fuzzy matching queries like `similarity(normalized_name, 'kallax') > 0.3`.

### `post_entities` — Which Entities Appear in Which Reels

A junction table linking posts to entities. Each link has a `relationship` type (mentions, reviews, features, recommends) and optional `context` explaining the entity's role in that reel (e.g., "Main subject of the tutorial").

### `entity_relations` — How Entities Relate to Each Other

Captures relationships between entities themselves:
- `pairs_with` — "KALLAX Shelf" pairs_with "SKÅDIS Pegboard"
- `made_by` — "KALLAX Shelf" made_by "IKEA"
- `fits_style` — "KALLAX Shelf" fits_style "Scandinavian Minimalist"
- `similar_to` — "KALLAX Shelf" similar_to "Target Cube Organizer"
- `alternative_to` — "Oat Milk" alternative_to "Almond Milk"

The `strength` column counts how many times a relationship has been observed across reels. If 5 different reels pair KALLAX with SKÅDIS, the strength is 5 — a strong signal.

### How It Forms a Knowledge Graph

These four tables together create a graph:

```
[Post A] --mentions--> [IKEA KALLAX Shelf] --made_by--> [IKEA]
[Post A] --features--> [SKÅDIS Pegboard]   --pairs_with-> [IKEA KALLAX Shelf]
[Post B] --reviews---> [IKEA KALLAX Shelf]  --fits_style-> [Scandinavian Minimalist]
[Post C] --mentions--> [IKEA KALLAX Shelf]  --alternative_to-> [Target Cube Organizer]
```

When a user searches for "IKEA shelf alternatives," the system can:
1. Find the "IKEA KALLAX Shelf" entity
2. Traverse `alternative_to` relationships to find "Target Cube Organizer"
3. Find all posts mentioning either entity
4. Return ranked results

---

## The Enrichment Pipeline

When a user saves a reel URL, the system runs a multi-step background pipeline. The API returns immediately with `status: pending` — the user can poll `GET /api/reels/{id}/status` to check progress.

The pipeline is orchestrated by `app/services/ingest.py`, which chains each step in sequence, updating the database after each one. If any step fails, the post is marked `status: failed` and the error is logged.

All blocking I/O (yt-dlp downloads, ffmpeg, external API calls) is wrapped with `asyncio.to_thread()` so the event loop stays responsive. Each step uses its own short-lived DB session to avoid holding transactions open during long external calls.

Temporary files (audio, video, frames) are created in a temp directory and cleaned up when the pipeline finishes, regardless of success or failure.

### Step 1: Save (Instant)
Validate the URL (must be Instagram, YouTube, or TikTok), check for duplicates, insert a `posts` row with `status = 'pending'`, and return immediately. The background pipeline starts via `asyncio.create_task()`.

### Step 2: Fetch Metadata (`app/services/metadata.py`)
Uses `yt-dlp` to extract: caption/description, creator name, thumbnail URL, video duration, and platform-specific metadata. The `_fetch_info()` function calls yt-dlp's `extract_info()` without downloading, purely to grab metadata.

The metadata service also handles media download:
- **Audio**: `_download_audio()` downloads the best audio stream and converts to mp3 via ffmpeg post-processing
- **Video**: `_download_video()` downloads video capped at 720p to keep file sizes manageable

Both functions are blocking (yt-dlp is synchronous) and run via `asyncio.to_thread()`.

### Step 3: Extract Video Frames (`app/services/metadata.py`)
`_extract_frames()` uses `ffprobe` to get video duration, then `ffmpeg` to extract 3 key frames at 25%, 50%, and 75% of the video duration. Each ffmpeg call has a 30-second timeout. These frames capture representative moments for visual analysis.

### Step 4: Transcribe Audio (`app/services/transcription.py`)
Sends the downloaded mp3 to OpenAI's Whisper API (`whisper-1` model). Returns the full text transcription of everything spoken in the reel. If there's no speech (e.g., music-only reels), returns an empty string — that's fine, the visual and caption content still provide value.

The service gracefully handles missing API keys (logs a warning and returns empty string) so the pipeline can run in development without OpenAI credentials.

### Step 5: Describe Frames + OCR (`app/services/vision.py`)
Sends the extracted frames to OpenAI's GPT-4o Vision in a single API call. Each frame is base64-encoded and sent as an `image_url` content block. The prompt asks for both a **visual description** (what's happening, objects, products, setting, aesthetic) and **on-screen text transcription** (captions, subtitles, product names, recipe steps, labels). This captures information that isn't in the audio or caption.

Like transcription, vision gracefully skips if no API key is configured or if no frames were extracted.

### Step 6: Entity Extraction — The Core (`app/services/extraction.py` + `app/prompts/extraction.py`)

This is the most important step in the pipeline. It uses LangChain to chain together a prompt template, OpenAI GPT-4o (at `temperature=0`), and a `JsonOutputParser` into a single invocable chain.

The prompt (`app/prompts/extraction.py`) concatenates caption + transcript + frame description into one text block and asks GPT-4o to return structured JSON with:
- **Entities** with specific names, types (product, brand, place, book, etc.), and flexible attributes
- **Relationships** between entities (pairs_with, made_by, fits_style, similar_to, alternative_to, part_of)
- **Tags** (8-15 lowercase, descriptive, searchable tags)
- **Content type** (tutorial, review, haul, recipe, workout, etc.)
- **Mood** (enthusiastic, calm, educational, etc.)
- **Summary** (2-3 sentences)

Key design decisions in the prompt:
- **Specificity**: "IKEA KALLAX Shelf" not "shelf" — specificity enables precise search
- **Multi-source extraction**: entities from caption, transcript, AND visual description
- **Background entities**: the coffee table behind the main product is still searchable content
- **Brands as separate entities**: "IKEA" is extracted as a brand entity with a `made_by` relationship to products

The extraction service (`app/services/extraction.py`) uses `chain.ainvoke()` for async execution. It validates that expected keys exist in the response (using `setdefault`) and returns an empty default structure on failure, so the pipeline can continue gracefully.

After extraction, the ingest pipeline stores `ai_summary`, `ai_tags`, `content_type`, and `mood` directly on the post row. The extracted entities and relationships are passed forward to the entity resolution step (Phase 4).

### Step 7: Entity Resolution (`app/services/resolution.py` + `app/prompts/resolution.py`)

For each extracted entity, runs a 3-step deduplication cascade against existing entities in the database:

1. **Exact match** on `normalized_name` + `type` — free, instant
2. **Fuzzy match** using pg_trgm `similarity()` with threshold > 0.3 — if the top candidate has similarity ≥ 0.85, it's accepted directly without LLM
3. **LLM judge** for ambiguous cases (similarity 0.3–0.85) — all uncertain pairs are batched into a single GPT-4o call to minimize API costs

The resolution function `resolve_and_persist_entities()` handles the full lifecycle in six phases:

- **Phase A**: Run each entity through exact → fuzzy matching, collecting ambiguous cases
- **Phase B**: Batch-send all ambiguous entities to the LLM judge in one call
- **Phase C**: Create new `Entity` rows for anything that didn't match
- **Phase D**: Update `mention_count` and merge new attributes for matched entities
- **Phase E**: Create `post_entity` links (using `ON CONFLICT DO NOTHING` to handle re-processing)
- **Phase F**: Create/update `entity_relations` rows (using `ON CONFLICT DO UPDATE` to increment `strength`)

Entity names are normalized via `normalize_entity_name()` — lowercase, strip whitespace, collapse internal spaces — before any matching.

### Step 8: Generate Embedding (`app/services/embedding.py`)

Combines the AI summary + all entity names + all tags into a single text string via `build_embedding_text()`, then generates a 1536-dimensional vector via OpenAI's `text-embedding-3-small` model. The embedding is stored on the `posts.embedding` column and powers Tier 3 (vector similarity) of the search engine.

Like other external API calls, embedding generation is wrapped in `asyncio.to_thread()` and gracefully returns `None` if the API key is missing or the call fails. The post is still marked `status="ready"` — it just won't appear in vector search results.

---

## Entity Extraction — The Core IP

The extraction prompt is the most important piece of the system. It determines what entities are found, how specific they are, and what attributes are captured.

Key design decisions in the prompt:

- **Be specific**: "IKEA KALLAX Shelf" not "shelf." Specificity enables precise search.
- **Extract from ALL sources**: Caption, transcript, AND visual. Many products are shown but never named aloud.
- **Include background entities**: The coffee table behind the main product is still searchable content.
- **Flexible attributes**: JSONB allows different attributes per entity type — price/color for products, cuisine/difficulty for recipes, author/genre for books.
- **Rich tags**: 8-15 tags covering topic, style, difficulty, setting, and target audience.
- **Structured JSON output**: LangChain's `JsonOutputParser` ensures the response is always valid, parseable JSON.

The extraction runs through LangChain with `temperature=0` for deterministic, consistent outputs.

---

## Entity Resolution — Deduplication Cascade

Without resolution, saving 10 reels about IKEA furniture would create 10 separate "KALLAX" entities with slightly different names. Resolution merges them into one entity with `mention_count = 10`.

The 3-step cascade:

### Step 1: Exact Match
Normalize the entity name (lowercase, strip whitespace) and query: `WHERE normalized_name = :name AND type = :type`. This catches identical mentions.

### Step 2: Fuzzy Match (pg_trgm)
If no exact match, use PostgreSQL's trigram similarity: `WHERE similarity(normalized_name, :name) > 0.3 ORDER BY similarity DESC LIMIT 5`. This catches near-matches like "KALLAX shelf" vs "KALLAX bookshelf" (similarity ~0.6).

### Step 3: LLM Judge
For matches in the 0.3-0.8 similarity range (ambiguous), batch all uncertain pairs into a single GPT-4o call. The LLM decides if they're the same real-world entity based on name, type, and attributes. Key rule: **false negatives are safer than false merges** — if unsure, keep them separate.

This cascade is efficient: most entities resolve at step 1 (free), some at step 2 (cheap Postgres query), and only ambiguous cases reach step 3 (one batched LLM call).

### Entity API Endpoints (`app/api/entities.py`)

Phase 4 also builds out the entity browsing API:

- **`GET /api/entities`** — List top entities sorted by `mention_count`, with optional `type` filter. This surfaces the most-referenced things across all saved reels.
- **`GET /api/entities/{id}`** — Full entity detail including all linked reels. Uses a JOIN through `post_entities` to return each reel's URL, summary, and the relationship type (mentions, reviews, features, recommends).
- **`GET /api/entities/{id}/related`** — Related entities via `entity_relations`, sorted by relationship strength. Queries both sides of the relation (entity can be `entity_a` or `entity_b`) using a CASE expression.

These endpoints let users browse the knowledge graph directly — see what entities the system has discovered, which reels mention them, and how entities relate to each other.

---

## The Knowledge Graph

The entity graph grows organically as users save more reels. Here's why this matters:

**Accumulating Context**: The first reel mentioning "KALLAX Shelf" might capture the name and brand. The second adds the price. The third adds a color variant. By the 10th reel, the entity has rich attributes from many sources.

**Emergent Relationships**: When multiple reels mention KALLAX and SKÅDIS together, the `pairs_with` relationship strength grows. High-strength relationships become strong search signals.

**Cross-Topic Discovery**: A user saves recipe reels and home decor reels separately. But if a reel mentions both "cast iron skillet" (kitchen product) and "open shelving" (home decor), the system links them. Searching "kitchen organization" now surfaces both recipe and decor reels.

---

## Hybrid Search Engine (`app/services/search.py` + `app/prompts/query.py`)

The search endpoint (`POST /api/search`) accepts a natural language query and returns ranked reels. The `hybrid_search()` function orchestrates four steps:

### Step 1: Query Decomposition

The raw query is sent to GPT-4o (`app/prompts/query.py`) which returns structured JSON:
- `entity_search` — specific entity names to look up (e.g., "KALLAX shelf", "IKEA")
- `tag_filters` — general topic tags to filter by (e.g., "home decor", "budget")
- `content_type` — optional filter (tutorial, review, recipe, etc.)
- `semantic_query` — a clean rephrasing of the full query for vector search

If the OpenAI API key is missing, decomposition is skipped and the raw query is used for semantic search only.

### Step 2: Three Search Tiers

**Tier 1 — Entity Graph Traversal (highest precision):**
Matches decomposed entity names against the `entities` table using both exact match and pg_trgm `similarity() > 0.3`, then JOINs through `post_entities` to find linked posts. Uses `DISTINCT ON (p.id)` to avoid duplicating posts that match multiple entities. Each result carries the name of the matched entity.

**Tier 2 — Tag Array Matching (medium precision):**
Uses Postgres array overlap (`&&`) against the `ai_tags` GIN index. Posts are scored by the fraction of query tags they match: `count(matching_tags) / total_query_tags`. Optionally filters by `content_type`. This catches conceptual matches not tied to specific entities.

**Tier 3 — Vector Cosine Similarity (catches everything else):**
Embeds the `semantic_query` via OpenAI `text-embedding-3-small`, then queries pgvector with `1 - (embedding <=> query_embedding)` as the score. This is the semantic fallback — it surfaces reels based on meaning even when no entities or tags match.

### Step 3: Reciprocal Rank Fusion (RRF)

Results from all three tiers are merged using RRF:

```
score(item) = Σ 1 / (k + rank_in_list)
```

Where `k = 60` dampens rank differences. Items appearing in multiple tiers with high ranks score highest. RRF is better than score averaging because each tier uses different score distributions (similarity percentages vs. tag fractions vs. cosine distances). Matched entity names from Tier 1 are carried through to the final results.

### Step 4: Return

Results are trimmed to the requested `limit` (default 20, max 100) and returned with `post_id`, `url`, `platform`, `ai_summary`, `score`, and `matched_entities`.

---

## Frontend

The frontend is a React SPA built with TypeScript, Vite, React Router, and Tailwind CSS. It runs as a separate service behind nginx, which proxies `/api/` requests to the backend.

### Auth Flow in the Frontend

- **`AuthContext`** (`frontend/src/contexts/AuthContext.tsx`) — Wraps the app and manages auth state. On mount, it calls `POST /api/auth/refresh` to restore sessions from the HttpOnly cookie. Provides `login()`, `register()`, `logout()`, and `user` to all components.
- **`ProtectedRoute`** (`frontend/src/components/ProtectedRoute.tsx`) — Wraps authenticated routes. Shows a loading spinner while checking auth, redirects to `/login` if not authenticated.
- **Token refresh** — The API client (`frontend/src/api/client.ts`) automatically retries on 401 by calling the refresh endpoint. If refresh fails, it redirects to `/login`.

### Pages

- **Login** — Username + password form at `/login`
- **Register** — Username + password + optional display name at `/register`, with client-side validation (min 3 chars, allowed characters)
- **Home** — Lists saved reels with status indicators, save button opens a modal
- **Search** — Natural language search with results showing matched entities
- **Entities** — Browse the knowledge graph, filter by type, see linked reels
- **Reel Detail** — Full reel info including transcript, summary, tags, and linked entities

### Layout

The `Layout` component provides:
- **Desktop**: Top navbar with nav links, "Save Reel" button, user display name, and logout
- **Mobile**: Sticky top bar with save + logout buttons, bottom tab nav for navigation

### Nginx Proxy

The frontend is served by nginx, which also proxies API requests to the backend. The nginx config uses `envsubst` templating for two variables:
- `$PORT` — The port to listen on (default 80, Railway assigns dynamically)
- `$API_UPSTREAM` — The backend URL (default `http://app:8000`, set to Railway internal URL in production)

---

## Production Hardening & Deployment

### Retry Logic

All external API calls (OpenAI Whisper, GPT-4o Vision, LLM extraction, embeddings) are wrapped with an async retry decorator (`app/services/retry.py`). On failure, each call retries up to 3 times with exponential backoff (1s, 2s, 4s delays). The outer try/except in each service still catches failures after all retries are exhausted, so the pipeline degrades gracefully.

### CORS Configuration

CORS origins are configurable via the `CORS_ORIGINS` environment variable (comma-separated). In development this defaults to `http://localhost:3000`. In production, set it to the frontend's public URL.

### Stats Endpoint

`GET /api/stats` returns processing statistics for the current user: reel counts by status (pending/processing/ready/failed), total entities, and total registered users.

### Deployment on Railway

The app deploys to Railway as three services:

1. **Postgres** — Railway's managed Postgres plugin (with pgvector)
2. **Backend** — Built from the root `Dockerfile`. Runs `alembic upgrade head` on startup, then starts uvicorn on `$PORT` (Railway assigns this dynamically)
3. **Frontend** — Built from `frontend/Dockerfile`. Nginx serves the React SPA and proxies `/api/` to the backend via Railway's internal networking

Railway configuration is defined in `railway.toml` (backend) and `frontend/railway.toml` with health checks and restart policies.

### CI Pipeline

GitHub Actions (`.github/workflows/ci.yml`) runs on every push/PR to `main`:
- **Backend**: Installs Python 3.12, runs `pytest` (unit tests only, no DB required)
- **Frontend**: Installs Node 20, runs `npm run build` to verify TypeScript compilation

---

## Tech Stack Rationale

| Choice | Why |
|---|---|
| **FastAPI** | Async-native, auto-generated Swagger docs for testing, lightweight. Perfect for an API-first project. |
| **PostgreSQL + pgvector** | One database for everything: structured data, vector search, and fuzzy text matching. No need for a separate vector DB. |
| **pg_trgm** | Free, fast fuzzy string matching built into Postgres. Powers entity resolution without any external service. |
| **SQLAlchemy 2.0 (async)** | Modern ORM with full async support. Alembic handles migrations. The `Mapped[]` annotation style provides type safety. |
| **LangChain** | Prompt templating, output parsing (JSON), and retry logic. Handles the boilerplate of LLM orchestration. |
| **OpenAI GPT-4o** | High-quality entity extraction, resolution, vision analysis, and query decomposition. All LLM calls go through a single provider for simplicity. |
| **Whisper API** | Industry-standard speech-to-text. Handles multiple languages and noisy audio (common in reels). |
| **OpenAI Embeddings** | `text-embedding-3-small` provides good quality at low cost and 1536 dimensions. |
| **yt-dlp** | The standard tool for downloading video/audio from any social media platform. Regularly updated to handle platform changes. |
| **bcrypt** | Direct `bcrypt` library for password hashing. Battle-tested, no wrapper libraries needed. |
| **python-jose** | JWT token creation and validation. Lightweight, supports HS256. |
| **React + TypeScript** | Type-safe frontend with Vite for fast builds. Tailwind CSS for utility-first styling. |
| **Docker Compose** | One-command startup for the entire stack. Postgres + backend + frontend, configured and networked automatically. |
| **Railway** | Simple container-based deployment. Managed Postgres, automatic builds from GitHub, internal service networking. |

---

## Project Structure

```
app/
├── main.py              # FastAPI app creation, lifespan events, CORS, router mounting
├── config.py            # Loads environment variables via Pydantic Settings
│
├── models/              # SQLAlchemy ORM models (one file per table)
│   ├── user.py          # User model — username, hashed_password, display_name
│   ├── post.py          # Post model — Vector and ARRAY columns, user_id FK
│   ├── entity.py        # Entity model with trigram index, user_id FK
│   ├── post_entity.py   # Junction table with relationship and context
│   └── entity_relation.py # Entity-to-entity relationships with strength
│
├── schemas/             # Pydantic models for API request/response validation
│   ├── auth.py          # RegisterRequest, LoginRequest, TokenResponse, UserResponse
│   ├── post.py          # URL validation, response serialization
│   ├── entity.py        # Entity response shapes
│   └── search.py        # Search request/response shapes
│
├── api/                 # Route handlers — thin layer that delegates to services
│   ├── deps.py          # get_current_user dependency (JWT + DB lookup)
│   ├── auth.py          # Register, login, refresh, logout, me endpoints
│   ├── posts.py         # CRUD endpoints for reels + stats endpoint
│   ├── entities.py      # Entity browsing endpoints
│   └── search.py        # Natural language search endpoint
│
├── services/            # Business logic — where the real work happens
│   ├── auth.py          # Password hashing (bcrypt), JWT creation, user lookup
│   ├── retry.py         # Async retry decorator with exponential backoff
│   ├── ingest.py        # Orchestrates the full enrichment pipeline
│   ├── metadata.py      # yt-dlp wrapper for fetching reel metadata
│   ├── transcription.py # Whisper API wrapper (with retry)
│   ├── vision.py        # GPT-4o Vision for frame analysis (with retry)
│   ├── extraction.py    # GPT-4o entity/tag extraction (with retry)
│   ├── resolution.py    # 3-step entity deduplication cascade (per-user scoped)
│   ├── embedding.py     # OpenAI embedding generation (with retry)
│   └── search.py        # Hybrid search engine with RRF merging (per-user scoped)
│
├── prompts/             # LLM prompt templates (separated for easy iteration)
│   ├── extraction.py    # Entity extraction system + user prompts
│   ├── resolution.py    # "Are these the same entity?" prompt
│   └── query.py         # Query decomposition prompt
│
└── db/
    ├── database.py      # Async SQLAlchemy engine, session factory, Base class
    └── migrations/      # Alembic migrations (001_initial + 002_add_auth)

frontend/
├── src/
│   ├── api/             # API client with token management and auto-refresh
│   │   ├── client.ts    # Core request helper, token injection, 401 retry
│   │   └── auth.ts      # Auth API functions (register, login, refresh, logout)
│   ├── contexts/
│   │   └── AuthContext.tsx # Auth state provider (user, login, logout, isAuthenticated)
│   ├── components/
│   │   ├── Layout.tsx       # App shell with nav, user menu, mobile bottom nav
│   │   ├── ProtectedRoute.tsx # Auth guard, redirects to /login
│   │   └── SaveReelModal.tsx  # URL input modal for saving reels
│   ├── pages/           # Login, Register, Home, Search, Entities, ReelDetail
│   └── types/           # TypeScript interfaces
├── nginx.conf.template  # Nginx config with $PORT and $API_UPSTREAM templating
├── Dockerfile           # Multi-stage: Node build → nginx with envsubst
└── railway.toml         # Railway deployment config
```

**Design principle**: Route handlers (`api/`) are thin — they validate input, call a service, and return a response. All business logic lives in `services/`. Prompts are separated into `prompts/` so they can be iterated on without touching service code.

---

## Build Phases

The project is built in 6 phases, each delivering a working increment:

| Phase | What It Delivers | Key Technologies |
|---|---|---|
| **1. Foundation** | Docker + Postgres + FastAPI CRUD for reels | Docker Compose, SQLAlchemy, Alembic |
| **2. Content Extraction** | Metadata fetch, audio transcription, frame description | yt-dlp, Whisper API, GPT-4o Vision |
| **3. Entity Extraction** | AI extracts entities, tags, relationships from content | LangChain, OpenAI GPT-4o |
| **4. Entity Resolution** | Deduplication + knowledge graph building | pg_trgm, GPT-4o for ambiguous cases |
| **5. Search Engine** | Hybrid natural language search | pgvector, OpenAI Embeddings, RRF |
| **5.5. Auth + Frontend** | Username/password auth, per-user isolation, React SPA | bcrypt, JWT, React, Tailwind CSS |
| **6. Polish + Deploy** | Retry logic, stats endpoint, Railway deployment | Railway, GitHub Actions, nginx |

Each phase builds on the previous one. Phase 1 is the foundation that everything else plugs into.
