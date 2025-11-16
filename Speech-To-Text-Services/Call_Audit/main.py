"""
main.py

This is the FastAPI entrypoint for the transcription service. It provides an
endpoint (`/transcribe-zip`) that accepts a request with a ZIP file URL
containing audio recordings, then orchestrates the full transcription and QA
pipeline.

"""

from __future__ import annotations

import asyncio
import time
from typing import Tuple

import httpx
from fastapi import FastAPI
from dotenv import load_dotenv
import os, shutil, tempfile

from config.settings import Settings
from domain.models import ZipTranscriptionRequest
from logger import get_logger
from services.pipeline import ZipTranscriptionPipeline
from services.transcription_client import TranscriptionClient
from services.callback_client import CallbackClient
from services.health_check import HealthCheck  
from helpers.file_utils import FileUtils
from services.qa_client import QaClient

load_dotenv()
logger = get_logger("Main")

app = FastAPI()
request_queue: asyncio.Queue[Tuple[ZipTranscriptionRequest, asyncio.Future]] = asyncio.Queue()

settings = Settings()
stt_client = TranscriptionClient(
    stt_url=settings.TRANSCRIBE_URL,
    model_id=settings.MODEL_ID,
    temperature=settings.TEMPERATURE,
    top_p=settings.TOP_P,
    repetition_penalty=settings.REPETITIONS_PENALTY,
    frequency_penalty=settings.FREQUENCY_PENALTY,
    retries=settings.RETRIES,
    timeout_sec=settings.HTTP_TIMEOUT_SEC,
)
callback_client = CallbackClient(timeout_sec=settings.HTTP_TIMEOUT_SEC)

@app.on_event("startup")
async def _startup() -> None:
    get_logger("startup").info("Background worker online")
    asyncio.create_task(_worker())

@app.post("/transcribe-zip")
async def transcribe_zip(req: ZipTranscriptionRequest):
    fut = asyncio.get_running_loop().create_future()
    await request_queue.put((req, fut))
    return await fut

async def _wait_if_stt_down(reason: str) -> None:
    """
    If STT health check fails, sleep for the configured backoff (8 minutes by default).
    """
    logger.warning("%s | STT seems down. Waiting %ss before resuming...",
                   reason, settings.HEALTH_BACKOFF_SEC)
    await asyncio.sleep(settings.HEALTH_BACKOFF_SEC)

async def _stt_is_healthy() -> bool:
    return await HealthCheck.check_service_health(
        url=settings.HEALTH_CHECK_URL,
        method=settings.HEALTH_CHECK_METHOD,
        expected_status=settings.HEALTH_CHECK_EXPECTED_STATUS,
        timeout_sec=settings.HEALTH_CHECK_TIMEOUT_SEC,
    )

def _is_transient_stt_error(exc: Exception) -> bool:
    """
    Treat connectivity/timeouts, HTTP 5xx, and our client's 'Server 5xx' RuntimeErrors as transient.
    """
    
    if isinstance(exc, httpx.RequestError):
        return True

    if isinstance(exc, httpx.HTTPStatusError):
        return 500 <= exc.response.status_code < 600

    msg = str(exc)
    if isinstance(exc, RuntimeError) and ("Server 5" in msg or "HTTP 5" in msg or "5xx" in msg):
        return True

    return False

async def _worker() -> None:
    while True:
        req, fut = await request_queue.get()
        try:
            healthy = await _stt_is_healthy()
            if not healthy:
                await _wait_if_stt_down("Pre-processing check failed")
        except Exception as e:
            logger.error("Health check error (pre): %r", e)
            await _wait_if_stt_down("Pre-processing check raised error")

        started = time.time()
        logger.info("Processing started | opportunity_id=%s | fileURL=%s | callback_url=%s",
                    req.opportunity_id, req.fileURL, req.callback_url)

        tmp_root = None
        try:
            try:
                tmp_root = tempfile.mkdtemp(prefix="zipproc_")
                audio_paths = FileUtils.download_and_extract_zip(req.fileURL, tmp_root)

                if not audio_paths:
                    msg = "No supported audio files found in ZIP."
                    logger.warning(msg)
                    fut.set_result({"status": "error", "message": msg})
                    continue

                for ap in audio_paths:
                    try:
                        dur = QaClient._get_audio_duration(ap)
                    except Exception as d_err:
                        logger.error("ffprobe failed for %s: %r", ap, d_err)
                        fut.set_result({"status": "error", "message": f"Failed to read duration for {os.path.basename(ap)}"})
                        break
                        
                    if dur > 2400:
                        msg = (f"Skipped: {os.path.basename(ap)} is {dur/60:.1f} mins "
                               f"(exceeds 40-minute limit).")
                        logger.warning(msg)
                        fut.set_result({"status": "skipped", "message": msg})
                        break
                else:
                    pass
                if fut.done():
                    continue
                while True:
                    try:
                        pipeline = ZipTranscriptionPipeline(settings, stt_client, callback_client)
                        await pipeline.handle(req, started)
                        fut.set_result({"status": "success", "message": "Data sent to callback URL."})
                        break
                    except Exception as exc:
                        if _is_transient_stt_error(exc):
                            logger.warning("STT transient/down during processing: %r", exc)
                            await _wait_if_stt_down("In-processing failure")
                            continue
                        else:
                            logger.error("Worker error (non-transient): %r", exc, exc_info=True)
                            fut.set_result({"status": "error", "message": str(exc)})
                            break

            except Exception as gate_err:
                logger.error("Pre-processing (download/extract/duration) failed: %r", gate_err, exc_info=True)
                fut.set_result({"status": "error", "message": "Failed to pre-process ZIP/duration"})
                continue

        finally:
            if tmp_root and os.path.isdir(tmp_root):
                shutil.rmtree(tmp_root, ignore_errors=True)
            request_queue.task_done()