import asyncio
import logging
import subprocess
import tempfile
from pathlib import Path

import httpx
import yt_dlp

logger = logging.getLogger(__name__)


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
    opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": False,
        "writesubtitles": False,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
    return {
        "caption": info.get("description", ""),
        "creator": info.get("uploader", ""),
        "platform": detect_platform(url),
        "metadata": {
            "duration": info.get("duration"),
            "thumbnail": info.get("thumbnail"),
            "like_count": info.get("like_count"),
            "view_count": info.get("view_count"),
            "platform_id": info.get("id"),
        },
    }


def _download_audio(url: str, output_dir: str) -> str | None:
    """Download audio as mp3 using yt-dlp (blocking). Returns path to mp3 file."""
    output_path = str(Path(output_dir) / "audio.%(ext)s")
    opts = {
        "format": "bestaudio/best",
        "outtmpl": output_path,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }
        ],
        "quiet": True,
        "no_warnings": True,
    }
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
    opts = {
        "format": "best[height<=720]/best",
        "outtmpl": output_path,
        "quiet": True,
        "no_warnings": True,
    }
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


def _download_thumbnail(thumbnail_url: str, dest_path: str) -> str | None:
    """Download a thumbnail image. Returns actual saved path (extension may differ)."""
    if not thumbnail_url:
        return None
    try:
        with httpx.Client(timeout=15, follow_redirects=True) as client:
            resp = client.get(thumbnail_url)
            resp.raise_for_status()
            # Detect actual format from content-type
            content_type = resp.headers.get("content-type", "")
            ext_map = {"image/webp": ".webp", "image/png": ".png", "image/jpeg": ".jpg"}
            ext = ext_map.get(content_type.split(";")[0].strip(), ".jpg")
            # Replace extension in dest_path
            actual_path = str(Path(dest_path).with_suffix(ext))
            Path(actual_path).write_bytes(resp.content)
            return actual_path
    except Exception:
        logger.warning("Failed to download thumbnail from %s", thumbnail_url)
        return None


async def fetch_metadata(url: str) -> dict:
    """Async wrapper: fetch reel metadata via yt-dlp."""
    return await asyncio.to_thread(_fetch_info, url)


async def download_thumbnail(thumbnail_url: str, dest_path: str) -> str | None:
    """Async wrapper: download thumbnail image. Returns saved path or None."""
    return await asyncio.to_thread(_download_thumbnail, thumbnail_url, dest_path)


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
