# 🗂️ Transcription Services – Voxtral

The **Voxtral Service** is a **FastAPI-based transcription microservice**.
It accepts a request with a **ZIP file of audio recordings**, processes the audio through the **Voxtral-24B (vLLM) speech-to-text model**, and delivers the results asynchronously to a **callback URL**.

---

## 🔎 How It Works

1. **POST `/transcribe-zip`**
   Clients send a JSON body containing:

   * `fileURL` → URL to a ZIP file of audio recordings
   * `opportunity_id` → Identifier for the transcription request
   * `callback_url` → Endpoint where results will be delivered

2. **Queued Processing**

   * Requests are placed into an internal async queue
   * A background worker (`_worker`) processes them sequentially to prevent overload

3. **Pipeline Execution**

   * Downloads and extracts the ZIP
   * Normalizes audio (e.g., WAV 16 kHz mono)
   * Transcribes using the **Voxtral STT model** via `TranscriptionClient`
   * Sends structured results to the provided `callback_url`

4. **Response**

   * API immediately returns a status (`success` or `error`)
   * Full transcription is pushed asynchronously to the callback endpoint

---

⚡ This design provides **asynchronous processing**, **scalability**, and **easy integration** with other systems.

---

## 1. 📁 Setup a Python Virtual Environment

> Recommended: **Python 3.10** for best compatibility.

### Create the environment

```bash
python3.10 -m venv voxtral_env
```

### Activate the environment

**Linux / macOS**

```bash
source voxtral_env/bin/activate
```

**Windows**

```powershell
voxtral_env\Scripts\activate
```

---

## 2. 📥 Install Requirements

```bash

sudo apt update
sudo apt install -y ffmpeg

cd Speech-To-Text-Services
pip install --use-deprecated=legacy-resolver -r voxtral_requirements.txt
```

---

## 3. 🚀 Run the Service

### Normal run

```bash
cd Speech-To-Text-Services/Call_Audit
python -m uvicorn main:app --host 0.0.0.0 --port 8002
```

### Background run with `nohup`

```bash
cd Speech-To-Text-Services/Call_Audit
nohup python -m uvicorn main:app --host 0.0.0.0 --port 8002 &
```

---

## 4. 📌 Notes

* Use `--reload` with `uvicorn` during development for auto-restart on code changes
* Adjust the `--port` to match your configuration