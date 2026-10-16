---
name: local-tts-narration
description: Generate voiceover audio locally from a reference voice with a Qwen3-TTS (AIKit/LocalAI) speech endpoint, then normalize and check the clips. Use for narration or voiceover for demos, screencasts, talks, walkthroughs, or any "read this script in my voice" request, and for revising or re-checking existing narration clips.
---

# Local TTS narration

Turn a script into per-clip narration WAVs using a local speech service, with loudness normalization, truncation guards, a cache that notices voice or model changes, and an honest content check. Nothing is uploaded: the reference voice and the script stay on the machine.

Helper: `$HOME/.agents/skills/local-tts-narration/scripts/narrate.py` (Python 3 standard library plus `ffmpeg`). Run it with `--help` for options.

## Workflow

1. **Find or start the service.** Reuse a running one; start a new one only when none exists. See [service setup](references/service-setup.md).

   ```sh
   narrate.py doctor --endpoint http://127.0.0.1:18080/v1/audio/speech
   ```

   `doctor` confirms the endpoint lists `qwen3-tts`. It does not prove the reference voice is mounted; the first clip does.

2. **Write the script for speech.** One paragraph or scene per clip, so a fix regenerates one clip. Write numbers the way they are spoken (see [writing for speech](references/writing-for-speech.md)). Provide it as plain text (blank lines separate clips), as JSON `{"clips": [{"id": "intro", "text": "..."}]}`, or as a storyboard whose `scenes[]` have `id` and `narration`. Clip ids match `[a-z0-9-]+`.

3. **Generate.** Pass the reference file and engine identity so the cache notices when either changes:

   ```sh
   narrate.py generate --script script.json --output-dir build/audio \
     --endpoint http://127.0.0.1:18080/v1/audio/speech \
     --voice /models/reference.wav \
     --reference-file /path/to/reference.wav \
     --engine-id "$(podman inspect --format '{{.Image}}' "$TTS_CONTAINER")"
   ```

   Output per clip: `<id>.wav` (48 kHz mono PCM16, -16 LUFS), `<id>-raw.wav`, `<id>-request.json`, `<id>-metadata.json`, plus `generation-report.json`. Use `--clip ID` (repeatable) to regenerate only some clips and `--force` to ignore the cache. Archive earlier takes before forcing.

4. **Check.** Exit status 2 from `generate` means a clip came close to its `max_frames` cap and may be cut off mid-sentence. Fix that clip (shorten, split, or raise `max_frames`) rather than trimming the video around it.

   ```sh
   narrate.py verify --script script.json --output-dir build/audio
   ```

   `verify` checks that each clip exists, matches the current script text and its recorded hash, is not silent, and is not near the cap. When `mlx_whisper` or `faster_whisper` is installed it also transcribes each clip and flags word-error or ending mismatches; otherwise the summary says `transcription: not performed`.

5. **Listen or say you did not.** A transcript match is not listening. Report which of these you actually did: integrity checks, automatic transcription, a person listening.

## Rules

- Keep the reference voice and any raw takes out of source control unless the user says otherwise. The reference is someone's voice.
- The service sees the script text. Only send it to an endpoint the user named or one you started yourself, bound to loopback.
- Clips are generated sequentially. Do not parallelize requests to a single local model.
- A changed reference WAV (same path), a new model image, or a changed `max_frames` makes cached clips stale. `generate` handles this only when you pass `--reference-file` and `--engine-id`; without them it warns that it cannot tell.
- Never trim narration to fit a video. Lengthen the scene or shorten the text.
- Read unfamiliar or numeric content aloud in your head: long decimals, currency, version strings, and acronyms are the usual failures. Fix them in the script, not in post.

## When something is wrong

| Symptom | Likely cause and fix |
| --- | --- |
| `cannot reach the TTS service` | Container stopped or wrong port. Check `podman ps` and the port mapping. |
| HTTP 4xx/5xx with a model or voice error | Model name differs from `qwen3-tts`, or the reference path is not the one mounted in the container. |
| Clip ends mid-sentence, `near_frame_cap` true | Text too long for `max_frames`. Split the clip or raise `max_frames` (default is derived from word count, max 768). |
| Clip repeats or skips words | Rewrite that sentence; very long or list-like sentences are fragile. |
| Wrong number or name | Spell it as spoken. Add the exact value on screen instead. |
| Volume differs between takes | Regenerate through `generate` so every clip is normalized to the same target; do not mix un-normalized raw clips. |
