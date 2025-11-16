"""
audio_utils.py

This module provides utility functions for working with audio files
using `ffmpeg` and `ffprobe`. These helpers are designed to integrate
with the transcription pipeline by ensuring all audio is in a standard
format (16 kHz, mono, PCM s16) and by enabling trimming and duration
extraction.

Methods:
1. _run:  
  Internal helper to run subprocess commands and capture stdout.

2. ffprobe_duration_seconds:
  Uses `ffprobe` to return the media duration in seconds. Returns `0.0`
  if ffprobe fails.

3. normalize_to_wav16k_mono:  
  Converts any input audio file into 16 kHz mono WAV (PCM s16). Returns
  the output file path.

4. ffmpeg_trim_to_wav16k_mono: 
  Trims a segment of audio to the specified start time and duration, and
  outputs it as 16 kHz mono WAV.

These utilities are critical for ensuring consistent input to the
speech-to-text (STT) transcription pipeline.
"""

from __future__ import annotations

import os
import subprocess
from typing import List

from logger import get_logger

log = get_logger("Audio Utils")


class AudioUtils:
    @staticmethod
    def _run(cmd: List[str]) -> str:
        """
        Run a subprocess and return stdout as text.
        Raises CalledProcessError on failure (so the caller sees real errors).
        """
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        return out.decode("utf-8", errors="ignore").strip()

    @staticmethod
    def ffprobe_duration_seconds(path: str) -> float:
        """
        Returns media duration (seconds) using ffprobe, or 0.0 on error.
        """
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=nw=1:nk=1", path,
        ]
        try:
            return float(AudioUtils._run(cmd))
        except Exception as e:
            log.error("ffprobe failed for %s: %s", path, repr(e))
            return 0.0

    @staticmethod
    def normalize_to_wav16k_mono(in_path: str, work_dir: str) -> str:
        """
        Convert input audio to WAV @ 16 kHz mono, PCM s16.
        Mirrors behavior needed by the pipeline.
        """
        dur = AudioUtils.ffprobe_duration_seconds(in_path)
        if dur <= 0.0:
            log.error("Audio file is empty or corrupt: %s", in_path)
            raise ValueError(f"Audio file is empty or corrupt: {in_path}")
            
        base = os.path.splitext(os.path.basename(in_path))[0]
        out_path = os.path.join(work_dir, f"{base}_16k_mono.wav")
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-i", in_path,
            "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
            out_path, "-y",
        ]
        AudioUtils._run(cmd)
        return out_path

    @staticmethod
    def ffmpeg_trim_to_wav16k_mono(in_path: str,start_sec: float,dur_sec: float,out_path: str) -> None:
        """
        Trim a segment and write it as WAV @ 16 kHz mono, PCM s16.
        """
        start_sec = max(0.0, float(start_sec))
        dur_sec = max(0.0, float(dur_sec))
        cmd = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-ss", f"{start_sec:.3f}", "-t", f"{dur_sec:.3f}",
            "-i", in_path,
            "-ar", "16000", "-ac", "1", "-sample_fmt", "s16",
            out_path, "-y",
        ]
        AudioUtils._run(cmd)
