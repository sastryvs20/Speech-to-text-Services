"""
transcription_client.py
-----------------------

This module defines the `TranscriptionClient` class, which is responsible for
interacting with a Speech-to-Text (STT) HTTP API using asynchronous I/O.

Key Responsibilities:
1. Prepare and send audio files (WAV format) to the STT endpoint for transcription.
2. Handle retries, timeouts, and error management for the HTTP POST requests.
3. Extract plain text from the JSON response (either from the "text" field
   or from individual "segments" if "text" is missing).
4. Provide a clean, reusable, single-responsibility client that can be plugged
   into a larger transcription pipeline.
"""

from __future__ import annotations

import os
import re
from typing import Any, Dict
import httpx

from logger import get_logger

log = get_logger("Transcription Client")

class TranscriptionClient:
    """
    Only handles STT HTTP I/O (SRP, DIP-friendly).
    """

    def __init__(self,stt_url: str,model_id: str,temperature: float,top_p: float,repetition_penalty: float,frequency_penalty: float,retries: int,timeout_sec: int):
        self.url = stt_url
        self.model = model_id
        self.temperature = temperature
        self.top_p = top_p
        self.repetition_penalty = repetition_penalty
        self.frequency_penalty = frequency_penalty
        self.retries = retries
        self.timeout_sec = timeout_sec

    async def transcribe_file(self, wav_path: str) -> Dict[str, Any]:
        mime = "audio/wav"
        data = {
            "model": self.model,
            "temperature": str(self.temperature),
            "top_p": str(self.top_p),
            "response_format": "json",
            "repetition_penalty": self.repetition_penalty,
            "frequency_penalty": self.frequency_penalty
        }

        last_err = None
        async with httpx.AsyncClient(timeout=self.timeout_sec) as client:
            for attempt in range(1, self.retries + 1):
                try:
                    with open(wav_path, "rb") as fh:
                        files = {"file": (os.path.basename(wav_path), fh, mime)}
                        resp = await client.post(self.url, data=data, files=files)
                    if resp.status_code == 200 and resp.headers.get("content-type", "").startswith("application/json"):
                        return resp.json()
                    last_err = RuntimeError(f"Server {resp.status_code}: {resp.text[:500]}")
                except Exception as e:
                    last_err = e
                if attempt < self.retries:
                    continue
                if last_err:
                    raise last_err
        return {}

    @staticmethod
    def extract_text(payload: Dict[str, Any]) -> str:
        if not isinstance(payload, dict):
            return ""
        t = (payload.get("text") or "").strip()
        if not t:
            segs = payload.get("segments") or []
            parts = [(s.get("text") or "").strip() for s in segs if (s.get("text") or "").strip()]
            t = " ".join(parts).strip()
        return re.sub(r"\s+", " ", t).strip()
