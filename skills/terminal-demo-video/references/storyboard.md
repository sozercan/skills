# Storyboard format

One JSON file drives both `narrate.py` (reads `id` and `narration`) and `build_video.py`.

```json
{
  "output": "my-demo",
  "label": "ACME / DEMO",
  "cast": "demo.cast",
  "footer_left": "Recorded execution  |  Waiting time compressed",
  "footer_right": "example.com/docs",
  "theme": {"background": "#1c1e20", "foreground": "#f4f2ec", "muted": "#b1b4ba", "accent": "#e8a1ee"},
  "scenes": [
    {"id": "intro", "type": "card", "title": "Ship a release in one command",
     "subtitle": "A recorded walkthrough", "narration": "Releases should not need a checklist. ..."},
    {"id": "install", "type": "chapter", "marker": "1 - Install", "title": "Install",
     "cue": "One package, no config", "narration": "First we install the tool. ...", "max_speed": 2},
    {"id": "outro", "type": "card", "title": "Try it yourself", "subtitle": "Next: wire it into CI",
     "link": "https://example.com/docs", "narration": "To get started, visit the link on screen."}
  ]
}
```

Paths (`cast`) are relative to the storyboard file. Scene ids match `[a-z0-9-]+` and are also the narration clip names.

## Top level

| Key | Meaning |
| --- | --- |
| `output` | Output basename (default: storyboard filename). |
| `label` | Small accent label on cards and chapter headers. |
| `cast` | Default recording for chapter scenes. |
| `footer_left` / `footer_right` | Footer strings on chapter scenes. |
| `theme` | Colors; any subset of the four keys. |

## Scenes

| Key | Applies to | Meaning |
| --- | --- | --- |
| `id`, `type` | all | `type` is `card` or `chapter`. |
| `narration` | all | Spoken text. Omit for a silent scene. |
| `title` | all | Card headline or chapter heading (default: the marker). |
| `subtitle`, `link`, `hold_seconds` | card | Secondary text, a URL shown in monospace, minimum seconds on screen (default 3). |
| `marker`, `cue`, `max_speed`, `cast`, `theme` | chapter | Recorded chapter label, one-line explanation under the title, maximum terminal speed-up (1-4, default 2), a different recording, and the agg terminal theme (default `monokai`). |

## Timing

A scene lasts long enough for 0.6 s of lead-in, the complete narration, and 1.8 s afterwards. A chapter also lasts at least its recorded length (capped at 40 s) and at least its length divided by `max_speed`, plus 1.2 s to hold the final terminal state. The terminal is sped up only as far as needed. If narration is longer than the recording, the last terminal frame is held.

Use `max_speed` above 2 only for repetitive output (batches, loops) and say so in the narration or on screen. Do not raise it to make a long scene fit; shorten the recording or split the chapter.

## Narration lines

Each narration block is one clip. Write for the ear (see `local-tts-narration`), keep each under about 100 words, and describe what the recorded run shows rather than inventing output. Open with the problem, explain a command before its result, and end with a useful next step and the link.
