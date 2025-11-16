"""health_check.py

This module provides a reusable HealthCheck utility for verifying the availability
of external services (such as transcription, STT, or any HTTP API). It uses the
httpx asynchronous client to send a request to the given URL and validate the 
response status code against an expected value.
"""

from __future__ import annotations

import httpx
from logger import get_logger

log = get_logger("Health Check")

class HealthCheck:
    @staticmethod
    async def check_service_health(*,url: str,method: str = "GET",expected_status: int = 200,timeout_sec: float = 5.0,) -> bool:
        """
        Returns True if calling `url` with `method` returns `expected_status`.
        """
        try:
            async with httpx.AsyncClient(timeout=timeout_sec) as client:
                resp = await client.request(method.upper(), url)
                ok = (resp.status_code == expected_status)
                if not ok:
                    log.warning(
                        "Health check non-OK status: %s (expected %s)",
                        resp.status_code, expected_status
                    )
                return ok
        except Exception as e:
            log.error("Health check failed for %s: %r", url, e)
            return False
