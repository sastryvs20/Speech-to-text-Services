"""
file_utils.py

This module provides helper functions for handling ZIP files containing
audio recordings and for extracting metadata (such as call dates) from
file names. It is a critical component of the transcription pipeline,
ensuring that audio files are properly downloaded, extracted, and ready
for processing.

Methods:

1. download_and_extract_zip:  
  Downloads and extracts audio files from a ZIP and returns a list of
  audio file paths.

2. extract_call_date:  
  Extracts only the call date from a filename, returning `YYYY-MM-DD`
  or an empty string.

These utilities simplify input preparation for the transcription
pipeline, keeping file handling logic separate from audio processing
and transcription logic.
"""

from __future__ import annotations

import os
import zipfile
import shutil
from typing import List
import requests
import re

from logger import get_logger

log = get_logger("File Utils")

class FileUtils:
    @staticmethod
    def download_and_extract_zip(zip_url: str, tmp_root: str) -> List[str]:
        """
        Downloads a ZIP to tmp_root and extracts audio files.
        Returns list of absolute audio file paths.
        """
        os.makedirs(tmp_root, exist_ok=True)
        zip_path = os.path.join(tmp_root, "input.zip")

        with requests.get(zip_url, stream=True, timeout=120) as r:
            r.raise_for_status()
            with open(zip_path, "wb") as f:
                shutil.copyfileobj(r.raw, f)

        audio_dir = os.path.join(tmp_root, "audios")
        os.makedirs(audio_dir, exist_ok=True)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(audio_dir)

        audio_paths: List[str] = []
        for root, _, files in os.walk(audio_dir):
            for name in files:
                lower = name.lower()
                if lower.endswith((".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg", ".wma")):
                    audio_paths.append(os.path.join(root, name))
        return audio_paths

    @staticmethod
    def extract_call_date(call_id: str) -> str:
        """
        Extract only the call date (ISO format) from the filename.
        Returns YYYY-MM-DD if found, otherwise "".
        """

        base = call_id

        # Case 1: Strict pattern with Y_M_D_H_M_S (e.g. 2025_09_18_11_38_20)
        dt_match = re.search(r"(2\d{3})_(\d{2})_(\d{2})_(\d{2})_(\d{2})_(\d{2})", base)
        if dt_match:
            y, m, d, hh, mm, ss = dt_match.groups()
            return f"{y}-{m}-{d}"

        # Case 2: Only Y_M_D present (e.g. 2025_09_18)
        d_match = re.search(r"(2\d{3})_(\d{2})_(\d{2})", base)
        if d_match:
            y, m, d = d_match.groups()
            return f"{y}-{m}-{d}"

        # Case 3: fallback - no valid date found
        return ""

