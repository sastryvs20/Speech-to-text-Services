"""
pipeline.py

ZipTranscriptionPipeline orchestrates the end-to-end flow for ZIP-based audio
transcription and (optional) QA prompts. It ties together helpers and services
to: download inputs, prepare audio, split into chunks, call STT, assemble a
single transcript per call, optionally run a first QA prompt, and finally POST
a consolidated JSON payload to a client-provided callback URL.
"""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Dict, List
import asyncio

from config.settings import Settings
from domain.models import ZipTranscriptionRequest
from logger import get_logger
from helpers.file_utils import (
    FileUtils
)
from helpers.audio_utils import (
    AudioUtils
)
from services.transcription_client import TranscriptionClient
from services.callback_client import CallbackClient
from services.qa_client import QaClient

log = get_logger("Pipeline")

class ZipTranscriptionPipeline:
    def __init__(self, settings: Settings, stt: TranscriptionClient, cb: CallbackClient):
        self.s = settings
        self.stt = stt
        self.cb = cb
       
        api_base = self.s.TRANSCRIBE_URL.rsplit("/v1/chat/completions", 1)[0] 
        self.qa = QaClient(
            chat_url=self.s.CHAT_API_BASE,                
            model_id=getattr(self.s, "CHAT_MODEL_ID", self.s.MODEL_ID),
            timeout_sec=self.s.HTTP_TIMEOUT_SEC,
            api_key=getattr(self.s, "API_KEY", "") or ""
        )


    def _compute_chunk_count(self, seconds: float, default_n: int) -> int:
        minutes = seconds / 60.0
        if 21.0 <= minutes < 30.0:
            return 5
        if 30.0 <= minutes < 40.0:
            return 6
        if minutes >= 40.0:
            return 7
        return max(1, default_n)

    def _split_into_n_with_buffer(self, in_wav: str, work_dir: str, n: int, buffer: float) -> List[str]:
        dur = AudioUtils.ffprobe_duration_seconds(in_wav)
        if dur <= 0 or n <= 1:
            single = os.path.join(work_dir, "part1.wav")
            AudioUtils.ffmpeg_trim_to_wav16k_mono(in_wav, 0.0, max(0.001, dur or 0.001), single)
            return [single]

        base = dur / float(n)
        chunks: List[str] = []
        for i in range(n):
            ideal_start = base * i
            ideal_end = base * (i + 1) if i < n - 1 else dur
            start = ideal_start if i == 0 else max(0.0, ideal_start - buffer)
            end = ideal_end
            part_dur = max(0.0, end - start)
            if part_dur <= 0.001:
                continue

            out_path = os.path.join(work_dir, f"part{i+1}.wav")
            AudioUtils.ffmpeg_trim_to_wav16k_mono(in_wav, start, part_dur, out_path)
            chunks.append(out_path)

        return chunks

    async def _call_with_retries(self,func,*args,retries: int = 2,timeout: float = 300.0,backoff_base: float = 1.0,**kwargs):
        attempt = 0
        last_err: Optional[Exception] = None
        while attempt <= retries:
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            except Exception as e:
                last_err = e
                log.warning("Call failed (attempt %d/%d): %r", attempt + 1, retries + 1, e)
                if attempt < retries:
                    await asyncio.sleep(backoff_base * (2 ** attempt))
            attempt += 1
        log.error("All attempts failed after %d tries. Last error: %r", retries + 1, last_err)
        return None

    
    async def _stt_transcribe_with_retries(self, path: str) -> Optional[Dict]:
        return await self._call_with_retries(self.stt.transcribe_file, path)

    async def handle(self, req: ZipTranscriptionRequest, started: float) -> None:
        with TemporaryDirectory(prefix="zip_work_") as tmp:
            audio_paths = FileUtils.download_and_extract_zip(req.fileURL, tmp)
            if not audio_paths:
                raise ValueError("ZIP contained no audio files")

            calls: List[Dict] = []
            log.info("Transcription started | files=%d | N_CHUNKS=%d | BUFFER_SEC=%.2f",len(audio_paths), self.s.N_CHUNKS, self.s.BUFFER_SEC)

            for audio_fp in audio_paths:
                base_filename = Path(audio_fp).name
                base = Path(audio_fp).stem
                call_date = FileUtils.extract_call_date(base_filename)
                wav_path = AudioUtils.normalize_to_wav16k_mono(audio_fp, tmp)

                dur_sec = AudioUtils.ffprobe_duration_seconds(wav_path)
                n_chunks = self._compute_chunk_count(dur_sec, self.s.N_CHUNKS)

                chunk_dir = Path(tmp) / f"{base}_chunks"
                chunk_dir.mkdir(parents=True, exist_ok=True)
                chunks = self._split_into_n_with_buffer(
                    wav_path, str(chunk_dir), n_chunks, self.s.BUFFER_SEC
                )

                log.info("Splitting | file=%s | duration=%.2fs (%.2f min) | chunks=%d | buffer=%.2fs",base_filename, dur_sec, dur_sec / 60.0, n_chunks, self.s.BUFFER_SEC)

                full_text_parts: List[str] = []
                for idx, cp in enumerate(chunks, start=1):
                    log.info("Uploading chunk %d/%d | file=%s | path=%s", idx, len(chunks), base_filename, cp)
                    stt_payload = await self._stt_transcribe_with_retries(cp)
                    if not stt_payload:
                
                        log.warning("STT failed for chunk %d/%d (%s). Continuing.", idx, len(chunks), cp)
                        continue
                    chunk_text = self.stt.extract_text(stt_payload)
                    if chunk_text:
                        full_text_parts.append(chunk_text)

                transcript = " ".join(x.strip() for x in full_text_parts if x.strip())


                introduction_and_opening = await self._call_with_retries(self.qa.ask_voxtral, wav_path, Settings.INTRODUCTION_AND_OPENING, temperature=0.01, top_p=0.01, repetition_penalty=Settings.REPETITIONS_PENALTY,
                                                                        frequency_penalty=Settings.FREQUENCY_PENALTY,max_tokens=256, max_completion_tokens=256)


                package_discussion_answer_1 = await self._call_with_retries(self.qa.ask_voxtral, wav_path=wav_path, question=Settings.PACKAGE_DISCUSSION_QUESTION_PART1, temperature=0.01,top_p=0.01,
                                                                        repetition_penalty=Settings.REPETITIONS_PENALTY,frequency_penalty=Settings.FREQUENCY_PENALTY,
                                                                        max_tokens=256,max_completion_tokens=256)
                package_discussion_answer_2 = await self._call_with_retries(self.qa.ask_voxtral, wav_path=wav_path, question=Settings.PACKAGE_DISCUSSION_QUESTION_PART2, temperature=0.01,top_p=0.01,
                                                                        repetition_penalty=Settings.REPETITIONS_PENALTY,frequency_penalty=Settings.FREQUENCY_PENALTY,
                                                                        max_tokens=256,max_completion_tokens=256)
                package_discussion_answer_3 = await self._call_with_retries(self.qa.ask_voxtral, wav_path=wav_path, question=Settings.PACKAGE_DISCUSSION_QUESTION_PART3, temperature=0.01,top_p=0.01,
                                                                        repetition_penalty=Settings.REPETITIONS_PENALTY,frequency_penalty=Settings.FREQUENCY_PENALTY,
                                                                        max_tokens=256,max_completion_tokens=256)

                agent_behavior_answer_1 = await self._call_with_retries(self.qa.ask_voxtral, wav_path=wav_path, question=Settings.AGENT_BEHAVIOR_QUESTION_PART1, temperature=0.01,top_p=0.01,
                                                                        repetition_penalty=Settings.REPETITIONS_PENALTY,frequency_penalty=Settings.FREQUENCY_PENALTY,
                                                                        max_tokens=256,max_completion_tokens=256)
                agent_behavior_answer_2 = await self._call_with_retries(self.qa.ask_voxtral, wav_path=wav_path, question=Settings.AGENT_BEHAVIOR_QUESTION_PART2, temperature=0.01,top_p=0.01,
                                                                        repetition_penalty=Settings.REPETITIONS_PENALTY,frequency_penalty=Settings.FREQUENCY_PENALTY,
                                                                        max_tokens=256,max_completion_tokens=256)

                closure = await self._call_with_retries(self.qa.ask_voxtral, wav_path=wav_path, question=Settings.CLOSURE, temperature=0.2, top_p=0.1, 
                                                                        repetition_penalty=Settings.REPETITIONS_PENALTY, frequency_penalty=Settings.FREQUENCY_PENALTY,
                                                                        max_completion_tokens=256, max_tokens=256)

                product_objection_handling = await self._call_with_retries(self.qa.ask_voxtral, wav_path=wav_path, question=Settings.PRODUCT_OBJECTION_HANDLING, temperature=0.2, top_p=0.1, 
                                                                        repetition_penalty=Settings.REPETITIONS_PENALTY, frequency_penalty=Settings.FREQUENCY_PENALTY,
                                                                        max_completion_tokens=256,max_tokens=256)

                package_discussion_answer = package_discussion_answer_1 + package_discussion_answer_2 + package_discussion_answer_3
                agent_behavior_answer = agent_behavior_answer_1 + agent_behavior_answer_2

                diarized_data: List[Dict[str, str]] = []
                if introduction_and_opening:
                    diarized_data.append({"First Question": introduction_and_opening})
                if package_discussion_answer:
                    diarized_data.append({"Package Discussion": package_discussion_answer})
                if agent_behavior_answer:
                    diarized_data.append({"Agent Behavior": agent_behavior_answer})
                if closure:
                    diarized_data.append({"Closure": closure})
                if(product_objection_handling):
                    diarized_data.append({"Product Objection Handling": product_objection_handling})                
                
                calls.append({
                    "call_id": base,
                    "call_date": call_date,
                    "duration": dur_sec,
                    "evidence_data": diarized_data,  
                    "transcript": transcript,          
                })

            payload = {"opportunity_id": req.opportunity_id, "calls": calls}
            await self.cb.post(req.callback_url, payload, started)
