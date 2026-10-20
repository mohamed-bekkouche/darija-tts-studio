# Dardja TTS Studio

Local web app to turn Algerian Darija audio into a TTS training dataset
for F5-TTS / KasbahTTS fine-tuning.

## Phase status

- **Phase 1 (current):** app skeleton, upload, background worker with stub pipeline
- Phase 2: real VAD + segmentation + transcription
- Phase 3: review UI
- Phase 4: export (CSV + ZIP)
- Phase 5: Heroku deployment

## Requirements

- macOS (tested on M-series)
- Python 3.11
- ffmpeg (`brew install ffmpeg`)

## Run

```bash
./run.sh# darija-tts-studio
