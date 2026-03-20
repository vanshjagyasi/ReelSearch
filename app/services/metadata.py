import asyncio
import base64
import io
import ipaddress
import logging
import os
import socket
import subprocess
import tempfile
from pathlib import Path
from urllib.parse import urlparse

import httpx
import yt_dlp
from PIL import Image

logger = logging.getLogger(__name__)

# Write cookies file once at module load if YTDLP_COOKIES env var is set
_COOKIES_PATH: str | None = None
_cookies_b64 = os.environ.get("YTDLP_COOKIES")
if _cookies_b64:
    try:
        _cookies_file = Path(tempfile.gettempdir()) / "ytdlp_cookies.txt"
        _cookies_file.write_bytes(base64.b64decode(_cookies_b64))
        _COOKIES_PATH = str(_cookies_file)
        logger.info("yt-dlp cookies loaded from YTDLP_COOKIES env var (%d bytes)", _cookies_file.stat().st_size)
    except Exception as e:
        logger.warning("Failed to decode YTDLP_COOKIES env var: %s", e)
else:
    logger.warning("YTDLP_COOKIES env var is NOT set — yt-dlp will run without cookies")


def _ydl_opts(**extra) -> dict:
    """Build yt-dlp options with cookies if available."""
    opts = {"quiet": True, "no_warnings": True}
    if _COOKIES_PATH:
        opts["cookiefile"] = _COOKIES_PATH
        logger.debug("Using cookies from %s", _COOKIES_PATH)
    else:
        logger.debug("No cookies available for yt-dlp")
    opts.update(extra)
    return opts


def _is_safe_url(url: str) -> bool:
    """Block private IPs and non-HTTP(S) schemes to prevent SSRF."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    try:
        ip = ipaddress.ip_address(socket.gethostbyname(parsed.hostname))
        return ip.is_global
    except (ValueError, socket.gaierror):
        return True  # Allow unresolvable hostnames (CDN domains)


def detect_platform(url: str) -> str:
    if "instagram.com" in url:
        return "instagram"
    if "youtube.com" in url or "youtu.be" in url:
        return "youtube"
    if "tiktok.com" in url:
        return "tiktok"
    return "unknown"


def _fetch_info(url: str) -> dict:
    """Extract metadata from a reel URL using yt-dlp (blocking)."""
    opts = _ydl_opts(extract_flat=False, writesubtitles=False)
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    thumbnail = info.get("thumbnail")
    logger.debug("yt-dlp thumbnail for %s: %s", url, thumbnail)
    logger.debug("yt-dlp thumbnails list: %s", info.get("thumbnails"))

    return {
        "caption": info.get("description", ""),
        "creator": info.get("uploader", ""),
        "platform": detect_platform(url),
        "metadata": {
            "duration": info.get("duration"),
            "thumbnail": thumbnail,
            "like_count": info.get("like_count"),
            "view_count": info.get("view_count"),
            "platform_id": info.get("id"),
        },
    }


def _download_audio(url: str, output_dir: str) -> str | None:
    """Download audio as mp3 using yt-dlp (blocking). Returns path to mp3 file."""
    output_path = str(Path(output_dir) / "audio.%(ext)s")
    opts = _ydl_opts(
        format="bestaudio/best",
        outtmpl=output_path,
        postprocessors=[
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }
        ],
    )
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        # yt-dlp replaces %(ext)s with the actual extension
        mp3_path = Path(output_dir) / "audio.mp3"
        if mp3_path.exists():
            return str(mp3_path)
        # Fallback: find any audio file in the dir
        for f in Path(output_dir).iterdir():
            if f.suffix in (".mp3", ".m4a", ".wav", ".ogg", ".opus"):
                return str(f)
        return None
    except Exception:
        logger.exception("Failed to download audio for %s", url)
        return None


def _download_video(url: str, output_dir: str) -> str | None:
    """Download video for frame extraction (blocking). Returns path to video file."""
    output_path = str(Path(output_dir) / "video.%(ext)s")
    opts = _ydl_opts(format="best[height<=720]/best", outtmpl=output_path)
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        for f in Path(output_dir).iterdir():
            if f.suffix in (".mp4", ".webm", ".mkv", ".mov"):
                return str(f)
        return None
    except Exception:
        logger.exception("Failed to download video for %s", url)
        return None


def _extract_frames(video_path: str, output_dir: str, num_frames: int = 3) -> list[str]:
    """Extract evenly-spaced key frames from a video using ffprobe + ffmpeg."""
    # Get duration
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                video_path,
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        duration = float(result.stdout.strip())
    except (ValueError, subprocess.TimeoutExpired):
        logger.warning("Could not determine video duration for %s", video_path)
        return []

    frames = []
    for i in range(num_frames):
        timestamp = duration * (i + 1) / (num_frames + 1)
        output_path = str(Path(output_dir) / f"frame_{i}.jpg")
        try:
            subprocess.run(
                [
                    "ffmpeg", "-ss", str(timestamp),
                    "-i", video_path,
                    "-vframes", "1", "-q:v", "2",
                    output_path, "-y",
                ],
                capture_output=True,
                timeout=30,
            )
            if Path(output_path).exists():
                frames.append(output_path)
        except subprocess.TimeoutExpired:
            logger.warning("Frame extraction timed out at %.1fs", timestamp)
    return frames


def _download_thumbnail_b64(thumbnail_url: str) -> str | None:
    """Download a thumbnail, resize to 320x320, return as base64 data URI."""
    if not thumbnail_url:
        return None
    if not _is_safe_url(thumbnail_url):
        logger.warning("Blocked unsafe thumbnail URL: %s", thumbnail_url)
        return None
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(thumbnail_url)
            resp.raise_for_status()
        img = Image.open(io.BytesIO(resp.content))
        img = img.convert("RGB")
        img.thumbnail((320, 320))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=80)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        logger.debug("Thumbnail compressed to %d bytes", buf.tell())
        return f"data:image/jpeg;base64,{b64}"
    except Exception:
        logger.warning("Failed to download/compress thumbnail from %s", thumbnail_url)
        return None


async def fetch_metadata(url: str) -> dict:
    """Async wrapper: fetch reel metadata via yt-dlp."""
    return await asyncio.to_thread(_fetch_info, url)


async def download_thumbnail_b64(thumbnail_url: str) -> str | None:
    """Async wrapper: download Instagram thumbnail, resize, return as base64 data URI."""
    return await asyncio.to_thread(_download_thumbnail_b64, thumbnail_url)


async def download_media(url: str, work_dir: str) -> dict:
    """Download audio and video, extract frames. Returns paths dict."""
    audio_path = await asyncio.to_thread(_download_audio, url, work_dir)
    video_path = await asyncio.to_thread(_download_video, url, work_dir)

    frames = []
    if video_path:
        frames = await asyncio.to_thread(_extract_frames, video_path, work_dir)

    return {
        "audio_path": audio_path,
        "video_path": video_path,
        "frame_paths": frames,
    }
