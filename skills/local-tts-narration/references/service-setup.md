# Service setup

The tested service is AIKit's `qwen3-tts` model behind a LocalAI-compatible API, run in Podman on Apple Silicon. Nothing here is required if you already have an endpoint that accepts the request below.

## Reuse before starting

Inspect existing containers with narrow output; a full `inspect` can print environment variables that hold credentials.

```sh
podman ps --format '{{.Names}}\t{{.Image}}\t{{.Ports}}'
podman inspect --format '{{.Image}} {{range .Mounts}}{{.Source}}->{{.Destination}} {{end}}' "$TTS_CONTAINER"
```

Reuse a container when its image is the one you want and its reference-voice mount is the voice you want. Then run `narrate.py doctor`.

## Start a task-owned service

Set `TTS_CONTAINER`, `TTS_IMAGE`, `TTS_PORT`, and the absolute `VOICE_REFERENCE` (a mono or stereo WAV of the voice, ideally 10-30 seconds of clean speech):

```sh
podman run -d --name "$TTS_CONTAINER" \
  --device /dev/dri \
  -p "127.0.0.1:$TTS_PORT:8080" \
  --mount "type=bind,source=$VOICE_REFERENCE,target=/models/reference.wav,readonly" \
  "$TTS_IMAGE" --config-file=/config.yaml
```

- Bind to loopback and mount the reference read-only. The request's `voice` is the path **inside** the container (`/models/reference.wav`).
- The validated image was `localhost/aikit-qwen3-tts:applesilicon` with a Podman VM that exposes `/dev/dri` (Virtio-GPU Venus). That is a property of the tested machine, not a promise for other Podman installs. If the container fails to start or runs without a GPU, report it; do not rebuild images or reconfigure the Podman VM unless asked.
- The AIKit model spec lives in the AIKit repository (`models/qwen3-tts-1.7b-base.yaml`, test at `scripts/ci/test-qwen3-tts.sh`; the validated configuration was on branch `feat/qwen3-tts-spec`). Read a branch with `git show <branch>:<path>` instead of switching a checkout that has other work in it.

## Request contract

```json
{
  "model": "qwen3-tts",
  "input": "The revised workflow used less hosted capacity.",
  "voice": "/models/reference.wav",
  "language": "en",
  "response_format": "wav",
  "params": {"max_frames": "768"}
}
```

`POST /v1/audio/speech` returns a WAV (`RIFF` header). `max_frames` bounds speech generation at 12.5 frames per second of audio, so 768 is about 61 seconds. It limits audio, not video frames. A WAV that stopped at the cap is still a valid WAV; `narrate.py` flags clips whose duration is within about 0.16 s of the cap.

## Cache identity

The cache keys on the request body plus the identity `narrate.py` records (`--reference-file` hash, `--engine-id`). The request body alone cannot see a new reference WAV at the same path or a new image behind the same endpoint, which is why those two options exist. After a voice or model change, regenerate every clip so the narration sounds like one speaker; do not mix takes.
