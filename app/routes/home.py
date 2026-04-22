import logging
import time
from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile
from fastapi import HTTPException
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.background import BackgroundTask

from app.utils.conversion import (
    OUTPUT_DIR,
    UPLOAD_DIR,
    convert_mp4_to_mp3,
    generate_file_paths,
    safe_delete,
    validate_upload_metadata,
    save_upload_file,
)


router = APIRouter()
templates = Jinja2Templates(directory="templates")
DELETE_OUTPUT_AFTER_SEND = True
REQUEST_COOLDOWN_SECONDS = 10
last_request_by_ip: dict[str, float] = {}
usage_stats = {"total_conversions": 0, "failed_conversions": 0}
logger = logging.getLogger(__name__)


def error_response(message: str, status_code: int) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"success": False, "error": message})


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/health")
async def health() -> JSONResponse:
    required_folders = {
        "uploads": UPLOAD_DIR,
        "outputs": OUTPUT_DIR,
        "templates": Path("templates"),
    }
    missing_folders = [name for name, path in required_folders.items() if not path.exists()]

    if missing_folders:
        return JSONResponse(
            status_code=500,
            content={
                "status": "error",
                "error": "Missing required folders.",
                "missing_folders": missing_folders,
            },
        )

    return JSONResponse(status_code=200, content={"status": "ok"})


@router.post("/convert")
async def convert(request: Request, file: UploadFile = File(...)) -> JSONResponse:
    # Keep endpoint focused on request/response while utility handles conversion details.
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    last_request_time = last_request_by_ip.get(client_ip)
    if last_request_time and now - last_request_time < REQUEST_COOLDOWN_SECONDS:
        return error_response(
            message="Too many requests. Please wait.",
            status_code=429,
        )
    last_request_by_ip[client_ip] = now

    input_path, output_path = generate_file_paths()

    try:
        validate_upload_metadata(file)
        logger.info("Upload started for client=%s filename=%s", client_ip, file.filename)
        await save_upload_file(file, input_path)
        logger.info("Conversion started for client=%s input=%s", client_ip, input_path.name)
        convert_mp4_to_mp3(input_path, output_path)
        usage_stats["total_conversions"] += 1
        logger.info("Conversion succeeded for client=%s output=%s", client_ip, output_path.name)
    except HTTPException as exc:
        usage_stats["failed_conversions"] += 1
        logger.warning("Conversion failed for client=%s reason=%s", client_ip, exc.detail)
        safe_delete(output_path)
        return error_response(message=str(exc.detail), status_code=exc.status_code)
    except Exception:
        usage_stats["failed_conversions"] += 1
        logger.exception("Conversion failed for client=%s due to unexpected error", client_ip)
        safe_delete(output_path)
        return error_response(message="Internal error during conversion.", status_code=500)
    finally:
        await file.close()
        safe_delete(input_path)

    download_id = output_path.stem
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "download_url": f"/download/{download_id}",
            "filename": "converted.mp3",
        },
    )


@router.get("/stats")
async def stats() -> JSONResponse:
    return JSONResponse(status_code=200, content=usage_stats)


@router.get("/download/{file_id}", response_model=None)
async def download(file_id: str):
    logger.info("Download requested for file_id=%s", file_id)
    if not file_id.replace("-", "").isalnum():
        return error_response(message="Invalid download id.", status_code=400)

    output_path = OUTPUT_DIR / f"{file_id}.mp3"
    if not output_path.exists():
        return error_response(message="File not found or already downloaded.", status_code=404)

    cleanup_task = BackgroundTask(safe_delete, output_path) if DELETE_OUTPUT_AFTER_SEND else None
    return FileResponse(
        path=output_path,
        media_type="audio/mpeg",
        filename="converted.mp3",
        background=cleanup_task,
    )
