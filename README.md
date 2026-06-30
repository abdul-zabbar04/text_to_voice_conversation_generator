# text_to_voice_conversation_generator

# Kokoro Conversation TTS — Backend

A Django REST Framework API that converts multi-speaker conversation scripts into a single merged MP3, using [Kokoro TTS](https://github.com/thewh1teagle/kokoro-onnx) running fully offline on CPU — no external API costs, no LLM required.

<!-- ![API example](docs/screenshots/api-example.png) -->

## Stack

`Django 6` · `Django REST Framework` · `Celery + Redis` · `Kokoro ONNX` · `pydub / ffmpeg`

## How it works

1. Client POSTs a script (`Speaker: text` format) with a voice assigned per speaker
2. API immediately returns a `job_id` — generation runs async via Celery
3. Client polls `/status/` until `completed`, then downloads the MP3

## API

```http
POST /api/conversation/generate/
{
  "script": "Host: Hello everyone.\nGuest1: Hi there.",
  "voice_map": { "Host": "am_adam", "Guest1": "af_sarah" },
  "keep_chunks": false
}

GET /api/conversation/{job_id}/status/
GET /api/conversation/voices/
```

## Setup

```bash
git clone <https://github.com/abdul-zabbar04/text_to_voice_conversation_generator.git>
cd kokoro_conversation_tts
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
sudo apt install ffmpeg espeak-ng redis-server
```

Download Kokoro model files into `models/`:

```bash
mkdir models && cd models
wget https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/kokoro-v1.0.onnx
wget https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/voices-v1.0.bin
cd ..
```

Start services (three terminals):

```bash
python manage.py migrate
redis-server
celery -A config worker --loglevel=info
python manage.py runserver
```

## Frontend

React + Vite frontend repo: [frontend repo](https://github.com/abdul-zabbar04/TTS-conversation-generator-frontend.git)
