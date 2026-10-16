#!/usr/bin/env python3
"""Generate, normalize and check voiceover clips from a local TTS service.

Targets an OpenAI-style `POST /v1/audio/speech` endpoint that clones a
reference voice (tested with AIKit's `qwen3-tts` model). Standard library
only, plus FFmpeg for loudness normalization.

  narrate.py doctor   --endpoint URL
  narrate.py generate --script FILE --output-dir DIR --endpoint URL --voice PATH
  narrate.py verify   --script FILE --output-dir DIR
"""

import argparse
import array
import datetime
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import wave

FRAMES_PER_SECOND = 12.5  # Qwen3-TTS codec frames per second of speech
SAMPLE_RATE = 48000
ID_PATTERN = re.compile(r"[a-z0-9-]+")
LOUDNESS = "loudnorm=I={target}:TP=-1.5:LRA=7"


def fail(message):
    raise SystemExit("narrate.py: " + message)


def sha256_file(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def sha256_json(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def load_clips(path):
    """Return [{id, text, max_frames?}] from a JSON or plain-text script.

    JSON may be {"clips": [...]} or a storyboard {"scenes": [...]}; text comes
    from `text` or `narration`, and items without text are skipped. Plain text
    is split into clips on blank lines.
    """
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    if path.suffix.lower() != ".json":
        paragraphs = [" ".join(block.split()) for block in re.split(r"\n\s*\n", raw) if block.strip()]
        items = [{"id": f"clip-{index:02d}", "text": text} for index, text in enumerate(paragraphs, 1)]
    else:
        document = json.loads(raw)
        source = document.get("clips", document.get("scenes")) if isinstance(document, dict) else document
        if not isinstance(source, list):
            fail("script JSON needs a 'clips' or 'scenes' list")
        items = []
        for item in source:
            text = item.get("text", item.get("narration"))
            if not text or not str(text).strip():
                continue
            clip = {"id": item.get("id"), "text": " ".join(str(text).split())}
            if "max_frames" in item:
                clip["max_frames"] = item["max_frames"]
            items.append(clip)
    seen = set()
    for item in items:
        if not isinstance(item["id"], str) or not ID_PATTERN.fullmatch(item["id"]):
            fail(f"clip id must match [a-z0-9-]+: {item['id']!r}")
        if item["id"] in seen:
            fail("duplicate clip id: " + item["id"])
        seen.add(item["id"])
    if not items:
        fail("script has no narration text")
    return items


def audio_metrics(path):
    with wave.open(str(path), "rb") as audio:
        rate, channels, width = audio.getframerate(), audio.getnchannels(), audio.getsampwidth()
        count = audio.getnframes()
        if width != 2:
            raise ValueError(f"expected PCM16 audio, received {width}-byte samples")
        samples = array.array("h", audio.readframes(count))
    if not samples:
        raise ValueError("audio has no samples")
    peak = max(abs(value) for value in samples) / 32768
    rms = math.sqrt(sum(value * value for value in samples) / len(samples)) / 32768
    return {
        "duration_seconds": round(count / (rate * channels), 6),
        "sample_rate": rate,
        "channels": channels,
        "rms_dbfs": round(20 * math.log10(rms), 2) if rms else None,
        "peak_dbfs": round(20 * math.log10(peak), 2) if peak else None,
        "sha256": sha256_file(path),
    }


def ffmpeg_json(command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        fail("ffmpeg failed: " + result.stderr[-2000:])
    match = re.search(r'\{\s*"input_i".*?\}', result.stderr, re.S)
    return json.loads(match.group(0)) if match else None


def normalize(raw, output, target_lufs):
    """Two-pass loudness normalization to 48 kHz mono PCM16."""
    target = LOUDNESS.format(target=target_lufs)
    levels = ffmpeg_json(["ffmpeg", "-hide_banner", "-nostdin", "-i", str(raw), "-af",
                          target + ":print_format=json", "-f", "null", "-"])
    if not levels:
        fail("ffmpeg returned no loudness measurements for " + str(raw))
    measured = (f"{target}:measured_I={levels['input_i']}:measured_TP={levels['input_tp']}"
                f":measured_LRA={levels['input_lra']}:measured_thresh={levels['input_thresh']}"
                f":offset={levels['target_offset']}:linear=true:print_format=json")
    return ffmpeg_json(["ffmpeg", "-hide_banner", "-nostdin", "-y", "-i", str(raw), "-af", measured,
                        "-ar", str(SAMPLE_RATE), "-ac", "1", "-c:a", "pcm_s16le", str(output)]) or levels


def default_max_frames(text):
    words = len(text.split())
    return min(768, max(160, math.ceil((words / 1.4 + 3) * FRAMES_PER_SECOND)))


def request_speech(args, payload):
    request = urllib.request.Request(
        args.endpoint, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            data = response.read()
            status, content_type = response.status, response.headers.get("Content-Type")
    except urllib.error.HTTPError as error:
        fail(f"TTS service returned HTTP {error.code}: {error.read()[:300]!r}")
    except (urllib.error.URLError, TimeoutError) as error:
        fail(f"cannot reach the TTS service at {args.endpoint}: {error}")
    if status != 200 or not data.startswith(b"RIFF"):
        fail("TTS service did not return a WAV")
    return data, {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "request_seconds": round(time.monotonic() - started, 3),
        "http_status": status,
        "content_type": content_type,
    }


def generate_clip(clip, args, identity, output_dir):
    clip_id, text = clip["id"], clip["text"]
    max_frames = clip.get("max_frames") or default_max_frames(text)
    payload = {
        "model": args.model,
        "input": text,
        "voice": args.voice,
        "language": args.language,
        "response_format": "wav",
        "params": {"max_frames": str(max_frames)},
    }
    request_record = {"payload": payload, "identity": identity}
    raw, final = output_dir / f"{clip_id}-raw.wav", output_dir / f"{clip_id}.wav"
    request_path, metadata_path = output_dir / f"{clip_id}-request.json", output_dir / f"{clip_id}-metadata.json"
    cached = (raw.exists() and request_path.exists()
              and json.loads(request_path.read_text()) == request_record)
    previous = json.loads(metadata_path.read_text()) if metadata_path.exists() else {}
    generation = previous.get("generation", {})
    if args.force or not cached:
        data, generation = request_speech(args, payload)
        raw.write_bytes(data)
        request_path.write_text(json.dumps(request_record, indent=2) + "\n")
        generation["cached"] = False
    else:
        generation = {**generation, "cached": True}
    raw_metrics = audio_metrics(raw)
    near_cap = raw_metrics["duration_seconds"] >= max_frames / FRAMES_PER_SECOND - 0.16
    loudness = normalize(raw, final, args.loudness)
    final_metrics = audio_metrics(final)
    metadata = {
        "id": clip_id,
        "text": text,
        "word_count": len(text.split()),
        "identity": identity,
        "generation": generation,
        "max_frames": max_frames,
        "near_frame_cap": near_cap,
        "raw": {"path": str(raw), **raw_metrics},
        "final": {"path": str(final), **final_metrics},
        "loudness": loudness,
    }
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    print(json.dumps({"id": clip_id, "seconds": final_metrics["duration_seconds"],
                      "cached": generation["cached"], "near_frame_cap": near_cap}), flush=True)
    return metadata


def build_identity(args):
    identity = {"model": args.model, "voice": args.voice}
    if args.reference_file:
        identity["reference_sha256"] = sha256_file(args.reference_file)
    if args.engine_id:
        identity["engine_id"] = args.engine_id
    return identity


def command_generate(args):
    clips = load_clips(args.script)
    if args.clip:
        unknown = set(args.clip) - {clip["id"] for clip in clips}
        if unknown:
            fail("unknown clip id(s): " + ", ".join(sorted(unknown)))
        clips = [clip for clip in clips if clip["id"] in args.clip]
    args.output_dir.mkdir(parents=True, exist_ok=True)
    identity = build_identity(args)
    if not (args.reference_file or args.engine_id):
        print("note: no --reference-file or --engine-id; the cache cannot notice a changed voice or model image",
              file=sys.stderr)
    results = [generate_clip(clip, args, identity, args.output_dir) for clip in clips]
    report = {
        "endpoint": args.endpoint,
        "identity": identity,
        "format": "48 kHz mono PCM16 WAV",
        "speech_seconds": round(sum(item["final"]["duration_seconds"] for item in results), 6),
        "clips": [{"id": item["id"], "seconds": item["final"]["duration_seconds"],
                   "near_frame_cap": item["near_frame_cap"], "sha256": item["final"]["sha256"]}
                  for item in results],
    }
    (args.output_dir / "generation-report.json").write_text(json.dumps(report, indent=2) + "\n")
    capped = [item["id"] for item in results if item["near_frame_cap"]]
    print(json.dumps({"clips": len(results), "speech_seconds": report["speech_seconds"],
                      "near_frame_cap": capped}))
    if capped:
        print("warning: possible truncation (shorten, split, or raise max_frames): " + ", ".join(capped),
              file=sys.stderr)
        return 2
    return 0


def command_doctor(args):
    models_url = re.sub(r"/audio/speech/?$", "/models", args.endpoint)
    if models_url == args.endpoint:
        models_url = args.endpoint.rstrip("/") + "/models"
    try:
        with urllib.request.urlopen(models_url, timeout=10) as response:
            body = json.loads(response.read())
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        fail(f"cannot read {models_url}: {error}")
    names = [item.get("id") for item in body.get("data", []) if isinstance(item, dict)]
    print(json.dumps({"models_url": models_url, "models": names, "has_model": args.model in names}))
    return 0 if args.model in names else 1


# --- verification ---------------------------------------------------------

NUMBER_WORDS = {"zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
                "seven": "7", "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12",
                "thirteen": "13", "fourteen": "14", "fifteen": "15", "sixteen": "16", "seventeen": "17",
                "eighteen": "18", "nineteen": "19", "twenty": "20", "thirty": "30", "forty": "40",
                "fifty": "50", "sixty": "60", "seventy": "70", "eighty": "80", "ninety": "90"}


def tokens(text):
    text = text.lower().replace("-", " ")
    text = re.sub(r"\b(" + "|".join(NUMBER_WORDS) + r")\b", lambda match: NUMBER_WORDS[match[0]], text)
    words = re.findall(r"[a-z0-9]+", text)
    merged = []
    for word in words:
        # "twenty three" -> "23": fold a ones digit into a preceding tens value.
        if (merged and word.isdigit() and len(word) == 1 and word != "0"
                and merged[-1].isdigit() and len(merged[-1]) == 2 and merged[-1].endswith("0")):
            merged[-1] = str(int(merged[-1]) + int(word))
        else:
            merged.append(word)
    return merged


def edit_distance(first, second):
    previous = list(range(len(second) + 1))
    for row, a in enumerate(first, 1):
        current = [row]
        for column, b in enumerate(second, 1):
            current.append(min(current[-1] + 1, previous[column] + 1, previous[column - 1] + (a != b)))
        previous = current
    return previous[-1]


def compare_transcript(expected, recognized):
    want, got = tokens(expected), tokens(recognized)
    error_rate = edit_distance(want, got) / max(1, len(want))
    ending = edit_distance(want[-7:], got[-7:])
    flags = []
    if error_rate > 0.14:
        flags.append("transcription_differs")
    if ending > 2:
        flags.append("check_ending")
    return round(error_rate, 4), flags


def make_transcriber(model):
    try:
        import mlx_whisper
    except ImportError:
        mlx_whisper = None
    if mlx_whisper:
        repo = model or "mlx-community/whisper-small.en-mlx"
        return ("mlx_whisper " + repo,
                lambda path: mlx_whisper.transcribe(str(path), path_or_hf_repo=repo, language="en",
                                                    verbose=None, temperature=0,
                                                    condition_on_previous_text=False)["text"])
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return None
    name = model or "small.en"
    engine = WhisperModel(name)
    return ("faster_whisper " + name,
            lambda path: " ".join(segment.text for segment in engine.transcribe(str(path), language="en")[0]))


def command_verify(args):
    clips = load_clips(args.script)
    transcriber = None if args.no_transcribe else make_transcriber(args.whisper_model)
    qa = args.output_dir / "audio-qa"
    qa.mkdir(exist_ok=True)
    results, problems = [], False
    for clip in clips:
        clip_id = clip["id"]
        metadata_path, wav = args.output_dir / f"{clip_id}-metadata.json", args.output_dir / f"{clip_id}.wav"
        flags = []
        entry = {"id": clip_id}
        if not metadata_path.exists() or not wav.exists():
            flags.append("missing")
        else:
            metadata = json.loads(metadata_path.read_text())
            if metadata["text"] != clip["text"]:
                flags.append("script_changed")
            if sha256_file(wav) != metadata["final"]["sha256"]:
                flags.append("audio_changed")
            if metadata["near_frame_cap"]:
                flags.append("frame_cap")
            try:
                metrics = audio_metrics(wav)
                if metrics["peak_dbfs"] is None or metrics["peak_dbfs"] < -50:
                    flags.append("silent")
            except ValueError:
                flags.append("unreadable")
            if transcriber and not (set(flags) & {"audio_changed", "unreadable"}):
                recognized = transcriber[1](wav)
                error_rate, extra = compare_transcript(clip["text"], recognized)
                flags.extend(extra)
                entry.update({"recognized": recognized.strip(), "word_error_rate": error_rate})
        entry["flags"] = flags
        problems = problems or bool(flags)
        (qa / f"{clip_id}.json").write_text(json.dumps(entry, indent=2) + "\n")
        results.append(entry)
        print(json.dumps({"id": clip_id, "flags": flags, "word_error_rate": entry.get("word_error_rate")}),
              flush=True)
    summary = {
        "transcription": transcriber[0] if transcriber else "not performed",
        "clips_checked": len(results),
        "flagged": [item["id"] for item in results if item["flags"]],
    }
    (qa / "summary.json").write_text(json.dumps({**summary, "clips": results}, indent=2) + "\n")
    print(json.dumps(summary))
    return 2 if problems else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="check that the service lists the model")
    doctor.add_argument("--endpoint", required=True)
    doctor.add_argument("--model", default="qwen3-tts")

    def script_args(command):
        command.add_argument("--script", type=Path, required=True,
                             help="clips JSON, storyboard JSON, or plain text (blank-line separated)")
        command.add_argument("--output-dir", type=Path, required=True)

    generate = sub.add_parser("generate", help="synthesize and normalize clips")
    script_args(generate)
    generate.add_argument("--endpoint", required=True, help="full URL, e.g. http://127.0.0.1:18080/v1/audio/speech")
    generate.add_argument("--voice", default="/models/reference.wav",
                          help="reference voice path as the service sees it")
    generate.add_argument("--reference-file", type=Path,
                          help="host path of the reference WAV; its hash joins the cache identity")
    generate.add_argument("--engine-id", help="model image or build identity to include in the cache identity")
    generate.add_argument("--model", default="qwen3-tts")
    generate.add_argument("--language", default="en")
    generate.add_argument("--loudness", type=float, default=-16.0, help="target LUFS (default -16)")
    generate.add_argument("--timeout", type=int, default=300)
    generate.add_argument("--clip", action="append", help="only this clip id; repeatable")
    generate.add_argument("--force", action="store_true", help="regenerate even when the cache matches")

    verify = sub.add_parser("verify", help="check clip integrity and, if a recognizer is installed, content")
    script_args(verify)
    verify.add_argument("--no-transcribe", action="store_true")
    verify.add_argument("--whisper-model", help="recognizer model name or repo")

    args = parser.parse_args()
    handler = {"doctor": command_doctor, "generate": command_generate, "verify": command_verify}[args.command]
    raise SystemExit(handler(args))


if __name__ == "__main__":
    main()
