from pathlib import Path
import subprocess
from typing import Final
from uuid import uuid4

from fastapi import HTTPException, UploadFile

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("outputs")
MAX_FILE_SIZE_BYTES: Final[int] = 500 * 1024 * 1024  # 500MB
CHUNK_SIZE_BYTES: Final[int] = 1024 * 1024  # 1MB
FFMPEG_TIMEOUT_SECONDS: Final[int] = 600  # 10 minutes
ALLOWED_MIME_TYPES = {"video/mp4", "application/mp4"}

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def safe_delete(path: Path) -> None:
    """Delete a file if it exists, without raising cleanup errors."""
    try:
        if path.exists():
            path.unlink()
    except OSError:
        pass


def validate_upload_metadata(file: UploadFile) -> None:
    """Validate filename and MIME type before processing."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file selected.")

    if not file.filename.lower().endswith(".mp4"):
        raise HTTPException(status_code=400, detail="Invalid file extension. Only .mp4 files are allowed.")

    if file.content_type and file.content_type.lower() not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail="Invalid MIME type. Only MP4 uploads are allowed.")


def generate_file_paths() -> tuple[Path, Path]:
    """Generate unique input/output paths for one conversion job."""
    file_stem = str(uuid4())
    return UPLOAD_DIR / f"{file_stem}.mp4", OUTPUT_DIR / f"{file_stem}.mp3"


async def save_upload_file(file: UploadFile, destination: Path) -> None:
    """Stream upload to disk in chunks with max size enforcement."""
    temp_path = destination.with_suffix(f"{destination.suffix}.part")
    total_size = 0

    try:
        with temp_path.open("wb", buffering=CHUNK_SIZE_BYTES) as buffer:
            while True:
                chunk = await file.read(CHUNK_SIZE_BYTES)
                if not chunk:
                    break

                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE_BYTES:
                    raise HTTPException(status_code=413, detail="File too large. Maximum size is 500MB.")

                buffer.write(chunk)

        if total_size == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        # Atomic replacement prevents partially written final files.
        temp_path.replace(destination)
    except Exception:
        safe_delete(temp_path)
        raise


def convert_mp4_to_mp3(input_path: Path, output_path: Path) -> None:
    """Run FFmpeg synchronously to convert MP4 audio stream to MP3."""
    command = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(input_path),
        "-vn",
        "-acodec",
        "libmp3lame",
        "-ab",
        "192k",
        "-ar",
        "44100",
        "-y",
        str(output_path),
    ]

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
            timeout=FFMPEG_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        safe_delete(output_path)
        raise HTTPException(status_code=504, detail="FFmpeg conversion timed out.")
    except OSError:
        safe_delete(output_path)
        raise HTTPException(status_code=500, detail="FFmpeg executable not available.")

    if result.returncode != 0:
        safe_delete(output_path)
        raise HTTPException(
            status_code=500,
            detail=f"FFmpeg conversion failed: {result.stderr.strip() or 'unknown error'}",
        )

    if not output_path.exists() or output_path.stat().st_size == 0:
        safe_delete(output_path)
        raise HTTPException(status_code=500, detail="FFmpeg conversion failed: output file was not created.")
