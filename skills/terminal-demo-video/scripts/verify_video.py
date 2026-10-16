#!/usr/bin/env python3
"""Verify an exported narrated demo against its build manifest.

  verify_video.py MANIFEST.json [--samples-dir DIR]

Checks (each reported separately; a skipped check says so):
  decode     the whole file decodes without errors, including its tail
  format     H.264 + AAC, 1920x1080, 30 fps, frame count equal to the manifest
  levels     the audio is audible and does not clip
  placement  each narration clip appears in the export within one video frame of
             its planned position (needs numpy; otherwise "not performed")
  samples    mid-scene and end-of-scene JPEGs are written for visual review

Writes <manifest>.verify.json and exits 1 if any performed check failed. It
cannot tell you the video looks right or sounds right: look at the samples and
listen, and say which of those you did.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import wave

RATE = 8000
FPS = 30


def sh(command, **kwargs):
    return subprocess.run(command, capture_output=True, check=True, **kwargs)


def sha256_file(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def probe(path):
    return json.loads(sh(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-count_frames",
                          "-of", "json", str(path)], text=True).stdout)


def decode_audio(video):
    raw = sh(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-i", str(video), "-vn",
              "-ar", str(RATE), "-ac", "1", "-f", "f32le", "-"]).stdout
    return raw


def read_clip(path):
    with wave.open(str(path), "rb") as audio:
        data = audio.readframes(audio.getnframes())
        rate = audio.getframerate()
    return data, rate


def check_placement(np, audio, manifest):
    samples = np.frombuffer(audio, dtype="<f4").astype(np.float64)
    results = []
    for clip in manifest["audio"]:
        data, rate = read_clip(clip["path"])
        factor = rate // RATE
        expected = np.frombuffer(data, dtype="<i2").astype(np.float64) / 32768
        expected = expected[: len(expected) // factor * factor].reshape(-1, factor).mean(axis=1)
        planned = round(clip["start_sample"] / rate * RATE)
        margin = RATE // FPS * 3
        lo = max(0, planned - margin)
        window = samples[lo:planned + len(expected) + margin]
        if len(window) < len(expected):
            results.append({"id": clip["id"], "ok": False, "error": "narration missing from the end of the export"})
            continue
        size = 1 << (len(window) + len(expected)).bit_length()
        scores = np.fft.irfft(np.fft.rfft(window, size) * np.conj(np.fft.rfft(expected, size)), size)
        scores = scores[: len(window) - len(expected) + 1]
        best = int(np.argmax(scores))
        actual = window[best:best + len(expected)]
        norm = math.sqrt(float(np.dot(actual, actual) * np.dot(expected, expected)))
        similarity = float(np.dot(actual, expected) / norm) if norm else 0.0
        shift = (lo + best - planned) / RATE
        results.append({"id": clip["id"], "correlation": round(similarity, 4), "shift_seconds": round(shift, 4),
                        "ok": similarity > 0.9 and abs(shift) <= 1 / FPS})
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--samples-dir", type=Path)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    video = Path(manifest["video"])
    report = {"video": str(video), "video_sha256": sha256_file(video), "checks": {}}
    checks = report["checks"]

    try:
        sh(["ffmpeg", "-hide_banner", "-loglevel", "error", "-xerror", "-nostdin", "-i", str(video), "-f", "null", "-"])
        checks["decode"] = {"ok": True}
    except subprocess.CalledProcessError as error:
        checks["decode"] = {"ok": False, "error": error.stderr.decode()[-500:]}

    info = probe(video)
    video_stream = next((s for s in info["streams"] if s["codec_type"] == "video"), {})
    audio_stream = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    frames = int(video_stream.get("nb_read_frames", 0))
    fmt = {"video_codec": video_stream.get("codec_name"), "size": [video_stream.get("width"), video_stream.get("height")],
           "fps": video_stream.get("r_frame_rate"), "frames": frames, "expected_frames": manifest["frames"],
           "audio_codec": audio_stream and audio_stream.get("codec_name")}
    fmt["ok"] = (fmt["video_codec"] == "h264" and fmt["size"] == manifest["size"]
                 and fmt["fps"] == f"{manifest['fps']}/1" and frames == manifest["frames"]
                 and fmt["audio_codec"] == "aac")
    checks["format"] = fmt

    try:
        import numpy as np
    except ImportError:
        np = None
    if manifest["audio"]:
        audio = decode_audio(video)
        if np is not None:
            peak = float(np.max(np.abs(np.frombuffer(audio, dtype="<f4")))) if audio else 0.0
        else:
            import array
            values = array.array("f")
            values.frombytes(audio)
            peak = max((abs(v) for v in values), default=0.0)
        checks["levels"] = {"peak_dbfs": round(20 * math.log10(peak), 2) if peak else None,
                            "ok": 0.01 < peak < 1}
        if np is not None:
            placement = check_placement(np, audio, manifest)
            checks["placement"] = {"clips": placement, "ok": all(item["ok"] for item in placement)}
        else:
            checks["placement"] = {"performed": False, "reason": "numpy not installed"}
    else:
        checks["levels"] = {"performed": False, "reason": "storyboard has no narration"}
        checks["placement"] = {"performed": False, "reason": "storyboard has no narration"}

    samples_dir = args.samples_dir or args.manifest.with_suffix(".samples")
    samples_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for index, scene in enumerate(manifest["scenes"]):
        start, length = scene["start_frame"] / FPS, scene["frames"] / FPS
        for label, offset in (("middle", length / 2), ("end", max(0.0, length - 0.5))):
            path = samples_dir / f"{index:02d}-{scene['id']}-{label}.jpg"
            sh(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-ss", f"{start + offset:.3f}",
                "-i", str(video), "-frames:v", "1", str(path)])
            written.append(str(path))
    checks["samples"] = {"files": written, "ok": all(Path(p).stat().st_size > 0 for p in written),
                         "note": "Written for visual review; this script did not look at them."}

    failed = [name for name, result in checks.items() if result.get("performed", True) and not result["ok"]]
    skipped = [name for name, result in checks.items() if result.get("performed") is False]
    report.update({"failed": failed, "not_performed": skipped,
                   "not_checked_by_this_script": ["visual review of the sample frames", "listening to the narration"]})
    out = args.manifest.with_suffix(".verify.json")
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"failed": failed, "not_performed": skipped, "report": str(out)}))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
