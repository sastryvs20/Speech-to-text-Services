"""
models.py

This module defines Pydantic request models used by the transcription service.

Represents the request body expected by the `/transcribe-zip` endpoint.

Fields:
- ""opportunity_id"" (str): Unique identifier for the business opportunity
   or case associated with the audio files.
- ""fileURL"" (str): Publicly accessible URL of a ZIP file containing
   one or more audio files to be transcribed.
- ""callback_url"" (str): URL where the service should send the final
   transcription results once processing is complete.
"""

from pydantic import BaseModel

class ZipTranscriptionRequest(BaseModel):
    opportunity_id: str
    fileURL: str
    callback_url: str
