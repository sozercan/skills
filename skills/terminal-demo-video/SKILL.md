---
name: terminal-demo-video
description: Record a terminal demo with asciinema and produce a narrated 1080p MP4 using a local voice (pairs with local-tts-narration). Use when asked to record, script, narrate, voice over, or render a CLI or terminal demo, walkthrough, or screencast video, or to revise, re-time, or verify one.
---

# Terminal demo video

Real recording in, narrated MP4 out. The terminal footage is a genuine asciinema capture (waiting time compressed, output bytes untouched), narration comes from [`local-tts-narration`](../local-tts-narration/SKILL.md), and `ffmpeg` assembles and checks the result. No video editor is required.

Helpers live in `$HOME/.agents/skills/terminal-demo-video/scripts/` and need Python 3, `ffmpeg`/`ffprobe`, [`agg`](https://github.com/asciinema/agg), and Python `pillow` (plus `numpy` for the audio-placement check).

| Script | Purpose |
| --- | --- |
| `cast.py check` | Validate a recording: exit status, chapter markers, optional secret scan. |
| `cast.py markers` | Turn `DemoMarker` escape sequences in the output into marker events. |
| `cast.py split` | Extract one chapter as its own cast. |
| `build_video.py` | Storyboard + cast + narration clips to `<name>.mp4` and a manifest. |
| `verify_video.py` | Decode, format, level, narration-placement checks and sample frames. |

## Workflow

Do the phases the user asked for. "Rehearse", "plan", or "don't record yet" means stop before recording. Resume at the first incomplete phase and reuse accepted assets whose inputs have not changed.

1. **Story.** Start from the viewer's problem and the outcome they want. Introduce each concept when it first appears and say what a command shows before showing it. Decide the chapters (one idea each) and write the storyboard ([format](references/storyboard.md)). Note any facts the demo depends on, and what is synthetic input versus observed result.
2. **Rehearse, then record.** Make the demo script deterministic and run it end to end before recording. Emit chapter markers, record with asciinema, then check the result ([recording guide](references/recording.md)).
   ```sh
   cast.py markers demo.cast
   cast.py check demo.cast --scan-secrets
   ```
   Accept the run only if it exits 0, has every chapter, shows the intended outcome, and has no secrets. An unexpected failure, retry, or fallback stays in the recording and gets narrated; do not edit it out.
3. **Narrate.** Write each scene's `narration` in the storyboard, then use `local-tts-narration` to generate and check clips with the same storyboard as the script (`narrate.py generate --script storyboard.json ...`). Never trim narration to fit; the scene stretches around it.
4. **Build.**
   ```sh
   build_video.py storyboard.json --audio-dir build/audio --output-dir build/video
   ```
   Output: `<name>.mp4`, `<name>.manifest.json` (scene frames, narration sample offsets, source hashes), and cached per-scene renders. Narration plays at its original speed; terminal playback is sped up only when the scene would otherwise be longer than its narration, up to each scene's `max_speed` (default 2, maximum 4).
5. **Verify.**
   ```sh
   verify_video.py build/video/<name>.manifest.json
   ```
   Then actually look at the sample JPEGs it writes (opening, dense output, final lines, closing link) and, if you can, play the file and listen.
6. **Deliver.** Hand over the MP4, the original `.cast`, the storyboard, and the manifest. Keep earlier editions when you revise rather than overwriting them.

## Rules

- The original `.cast` is evidence. Never edit it; presentation copies are generated from it.
- Use the real CLI and ordinary shell commands in the walkthrough. Keep installs, image builds, and credential setup off camera, and keep credentials and anything the user excluded out of the recording. A secret scan is a heuristic; read the output yourself.
- Report only checks you ran, and keep them separate: decoded cleanly, narration placed correctly, frames visually inspected, played back, a person listened. `verify_video.py` covers the first two (and writes frames for the third).
- Changing a cast invalidates its scenes; changing a narration line invalidates that clip and its scene. Everything else can be reused. `build_video.py` caches scenes by input hash.
- Format is fixed at 1920x1080, 30 fps, H.264 + AAC. Say so if the user needs something else; it is a change to the script, not a flag.

## When something is wrong

| Symptom | Fix |
| --- | --- |
| `cast.py` says expected asciicast v3 | `asciinema convert -f asciicast-v3 in.cast out.cast`. |
| No markers found | The demo script did not print the marker escape, or `cast.py markers` was not run. See the recording guide. |
| `marker ... not in demo.cast` | The storyboard `marker` must match the label exactly, including punctuation. |
| `narration ... no longer matches the storyboard` | Script text changed after generating audio. Regenerate that clip. |
| `may be truncated (frame cap)` | Fix the clip in `local-tts-narration`; do not proceed. |
| Terminal text too small | Record with fewer columns (about 100) or shorter lines; the frame scales the terminal to fit. |
| Titles missing glyphs or wrong font | Pass `--font`, `--bold-font`, `--mono-font` (TTF/OTF paths). |
| Terminal font not what you want | `--agg-font-family "Menlo,DejaVu Sans Mono"`. |
