"""qa_client.py

Provides `QaClient`, a thin HTTP wrapper for sending **audio + instructions**
to a chat-completions style endpoint (e.g., `/v1/chat/completions`) and
retrieving a free-form, model-generated answer.
"""

from __future__ import annotations
import base64, subprocess
from pathlib import Path
from typing import Dict, Any, Optional
import httpx
from config.settings import Settings
import tempfile
import os

from config.settings import Settings
from logger import get_logger

log = get_logger("QA Client")


class QaClient:
    def __init__(self, chat_url: str, model_id: str, timeout_sec: int = 600, api_key: str = "") -> None:
        self.url = chat_url
        self.model = model_id
        self.timeout = timeout_sec
        self.headers = {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    @staticmethod
    def _wav16k_base64(path: str) -> Dict[str, str]:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Audio file not found: {path}")
        cmd = ["ffmpeg","-nostdin","-loglevel","error","-i",str(p),"-ac","1","-ar","16000","-f","wav","-"]
        out = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout
        return {"data": base64.b64encode(out).decode("utf-8"), "format": "wav"}

    @staticmethod
    def _get_audio_duration(path: str) -> float:
        """Return audio duration in seconds using ffprobe."""
        cmd = [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", path
        ]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        return float(result.stdout.strip())

    @staticmethod
    def _split_audio_into_two_chunks(path: str) -> List[str]:
        """
        Split audio file into 2 chunks using ffmpeg and return file paths.
        """
        duration = QaClient._get_audio_duration(path)
        half = duration / 2

        temp_files = []
        for i, start in enumerate([0, half]):
            out_path = tempfile.mktemp(suffix=f"_part{i+1}.wav")
            cmd = [
                "ffmpeg", "-nostdin", "-loglevel", "error",
                "-i", path, "-ss", str(start), "-t", str(half),
                "-ac", "1", "-ar", "16000", "-f", "wav", out_path
            ]
            subprocess.run(cmd, check=True)
            temp_files.append(out_path)
        return temp_files

    @staticmethod
    def _slice_first_seconds(path: str, seconds: int = 120) -> str:
        """
        Return a path to a file containing the first `seconds` of audio.
        If the original is shorter than or equal to `seconds`, returns the original path.
        """
        try:
            duration = QaClient._get_audio_duration(path)
        except Exception as e:
            try:
                log.warning("Duration check failed for %s: %r. Using original.", path, e)
            except NameError:
                pass
            return path

        if duration <= seconds:
            return path

        out_path = tempfile.mktemp(suffix="_first.wav")
        cmd = [
            "ffmpeg", "-nostdin", "-loglevel", "error",
            "-i", path, "-ss", "0", "-t", str(seconds),
            "-c", "copy", out_path
        ]
        try:
            subprocess.run(cmd, check=True)
            return out_path
        except Exception as e:
            try:
                log.error("Failed to slice first %ss from %s: %r. Using original.", seconds, path, e)
            except NameError:
                pass
            if os.path.exists(out_path):
                try: os.remove(out_path)
                except: pass
            return path

    """ API call logic for Voxtral"""

    async def ask_voxtral(self,wav_path: str,question: str,temperature: float ,top_p: float, repetition_penalty: float ,frequency_penalty: float ,max_tokens: int, max_completion_tokens: int) -> Optional[str]:

        audio = self._wav16k_base64(wav_path)
        payload: Dict[str, Any] = {
            "model": self.model,
            "temperature": temperature,
            "top_p": top_p,
            "repetition_penalty": repetition_penalty,
            "frequency_penalty": frequency_penalty,
            "max_completion_tokens": max_completion_tokens,
            "max_tokens": max_tokens,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "input_audio", "input_audio": audio},
                        {"type": "text", "text": question},
                    ],
                }
            ],
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            log.info("Analyzing QA prompt...")
            r = await client.post(self.url, json=payload, headers=self.headers)

        if r.status_code != 200:
            log.error("QA chat error: %s %s", r.status_code, (r.text or "")[:400])
            return None

        try:
            j = r.json()
        except Exception as e:
            log.error("QA chat JSON parse error: %r | body=%s", e, (r.text or "")[:400])
            return None

        msg = (j.get("choices") or [{}])[0].get("message", {})
        content = msg.get("content")

        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            parts: List[str] = []
            for p in content:
                if isinstance(p, dict):
                    t = p.get("text")
                    if isinstance(t, str) and t.strip():
                        parts.append(t.strip())
            joined = " ".join(parts).strip()
            return joined or None

        text = msg.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()

        return None

