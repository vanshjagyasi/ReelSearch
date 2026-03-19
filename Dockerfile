FROM python:3.12-slim

# Install system dependencies (ffmpeg for yt-dlp audio/video processing)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /code

# Install Python dependencies (cached layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

ENV PORT=8000
EXPOSE ${PORT}

CMD ["sh", "-c", "sysctl -w net.ipv6.bindv6only=0 2>/dev/null; alembic upgrade head && uvicorn app.main:app --host :: --port ${PORT:-8000}"]
