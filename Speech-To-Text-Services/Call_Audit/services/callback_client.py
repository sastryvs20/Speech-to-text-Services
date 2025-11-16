"""
callback_client.py

This module defines the ""CallbackClient"" class, which is responsible for
sending transcription results back to a client-defined callback URL.

Responsibilities:

1. Post a JSON payload (transcription results) to the callback URL.
"""

from __future__ import annotations

import json
import time
from typing import Dict
import httpx

from logger import get_logger

log = get_logger("Callback Client")

class CallbackClient:
    """
    Posts final payload to callback URL. Also logs callback result and total time.
    """

    def __init__(self, timeout_sec: int = 120) -> None:
        self.timeout_sec = timeout_sec

    async def post(self, url: str, payload: Dict, started: float) -> None:
        log.info("Transcription ended")
        log.info((json.dumps(payload, indent=2, ensure_ascii=False)))

        try:
            async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
                rsp = await client.post(url, json=payload)
            if rsp.status_code == 200:
                log.info("Callback result | status=%d | url=%s", rsp.status_code, url)
            else:
                body_preview = (rsp.text or "")[:500]
                log.error("Callback result | status=%d | url=%s | body=%r", rsp.status_code, url, body_preview)
        except httpx.RequestError as e:
            log.error("Callback error | url=%s | error=%s", url, repr(e), exc_info=True)
        finally:
            total_time = time.time() - started
            log.info("Total time | seconds=%.2f", total_time)
