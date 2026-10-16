"""Tests for cast.py, build_video.py and verify_video.py."""

import hashlib
import importlib.util
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import wave

SCRIPTS = Path(__file__).resolve().parents[2] / "skills/terminal-demo-video/scripts"
spec = importlib.util.spec_from_file_location("cast", SCRIPTS / "cast.py")
cast = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cast)

CAST = """{"version":3,"term":{"cols":100,"rows":28},"timestamp":1,"command":"demo"}
[0.1,"o","\\u001b[H\\u001b[2J"]
[0.0,"o","\\u001b]1337;DemoMarker=Say hello\\u0007"]
[0.2,"o","$ echo hello\\r\\n"]
[0.5,"o","hello\\r\\n"]
[0.0,"o","\\u001b]1337;DemoMarker=Count\\u0007"]
[0.3,"o","$ seq 1 3\\r\\n"]
[0.4,"o","1\\r\\n2\\r\\n3\\r\\n"]
[0.2,"x","0"]
"""


def run(script, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], capture_output=True, text=True)


class CastTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.path = self.tmp / "demo.cast"
        self.path.write_text(CAST)

    def test_markers_then_check_lists_chapters(self):
        self.assertEqual(run("cast.py", "markers", str(self.path)).returncode, 0)
        result = run("cast.py", "check", str(self.path))
        self.assertEqual(result.returncode, 0, result.stdout)
        report = json.loads(result.stdout)
        self.assertEqual([m["label"] for m in report["markers"]], ["Say hello", "Count"])
        self.assertEqual(report["exit_status"], "0")
        self.assertNotIn("DemoMarker", self.path.read_text())

    def test_check_fails_without_markers_or_exit_status(self):
        report = json.loads(run("cast.py", "check", str(self.path)).stdout)
        self.assertTrue(any("no chapter markers" in p for p in report["problems"]))
        interrupted = self.tmp / "cut.cast"
        interrupted.write_text("".join(CAST.splitlines(True)[:-1]))
        report = json.loads(run("cast.py", "check", str(interrupted)).stdout)
        self.assertTrue(any("no exit event" in p for p in report["problems"]))

    def test_check_flags_nonzero_exit_unless_allowed(self):
        failed = self.tmp / "failed.cast"
        failed.write_text(CAST.replace('"x","0"', '"x","1"'))
        run("cast.py", "markers", str(failed))
        self.assertEqual(run("cast.py", "check", str(failed)).returncode, 1)
        self.assertEqual(run("cast.py", "check", str(failed), "--allow-nonzero-exit").returncode, 0)

    def test_secret_scan_finds_token_in_output(self):
        leaky = self.tmp / "leaky.cast"
        token = "ghp_" + "a" * 36
        leaky.write_text(CAST.replace("hello\\r\\n", token + "\\r\\n"))
        run("cast.py", "markers", str(leaky))
        result = run("cast.py", "check", str(leaky), "--scan-secrets")
        self.assertEqual(result.returncode, 1)
        report = json.loads(result.stdout)
        self.assertEqual(report["secret_hits"][0]["kind"], "github token")
        self.assertNotIn(token, result.stdout)

    def test_rejects_v2_with_conversion_hint(self):
        old = self.tmp / "old.cast"
        old.write_text('{"version":2,"width":80,"height":24}\n[0.1,"o","x"]\n')
        result = run("cast.py", "check", str(old))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("asciinema convert", result.stderr)

    def test_split_keeps_recorded_output_bytes(self):
        run("cast.py", "markers", str(self.path))
        out = self.tmp / "chapter.cast"
        self.assertEqual(run("cast.py", "split", str(self.path), "--marker", "Count", "-o", str(out)).returncode, 0)
        _, events = cast.read_cast(out)
        shown = "".join(e[2] for e in events if e[1] == "o")
        self.assertIn("$ seq 1 3", shown)
        self.assertNotIn("echo hello", shown)
        self.assertEqual(events[-1], [0, "x", "0"])
        self.assertEqual(events[1][0], 0)

    def test_duplicate_markers_are_rejected(self):
        duplicate = self.tmp / "dup.cast"
        duplicate.write_text(CAST.replace("DemoMarker=Count", "DemoMarker=Say hello"))
        run("cast.py", "markers", str(duplicate))
        self.assertIn("duplicate marker", run("cast.py", "check", str(duplicate)).stderr)


def tone(path, seconds, rate=48000):
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(b"".join(
            struct.pack("<h", int(9000 * math.sin(2 * math.pi * (200 + 60 * (i // 4000 % 5)) * i / rate)))
            for i in range(int(seconds * rate))))


def have(*tools):
    return all(shutil.which(tool) for tool in tools)


def have_pillow():
    return importlib.util.find_spec("PIL") is not None


@unittest.skipUnless(have("ffmpeg", "ffprobe", "agg") and have_pillow(), "needs ffmpeg, agg and Pillow")
class BuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "demo.cast").write_text(CAST)
        run("cast.py", "markers", str(self.tmp / "demo.cast"))
        self.story = {"output": "demo", "label": "ACME / DEMO", "cast": "demo.cast", "scenes": [
            {"id": "intro", "type": "card", "title": "Hello", "subtitle": "A tiny walkthrough",
             "narration": "This is a short demo."},
            {"id": "hello", "type": "chapter", "marker": "Say hello", "title": "Say hello",
             "narration": "First we print a greeting."},
            {"id": "count", "type": "chapter", "marker": "Count", "title": "Count"},
            {"id": "outro", "type": "card", "title": "Done", "link": "https://example.com"}]}
        self.audio = self.tmp / "audio"
        self.audio.mkdir()
        for scene in self.story["scenes"]:
            if scene.get("narration"):
                self.write_clip(scene["id"], scene["narration"], 1.5)

    def write_clip(self, name, text, seconds):
        wav = self.audio / f"{name}.wav"
        tone(wav, seconds)
        (self.audio / f"{name}-metadata.json").write_text(json.dumps({
            "id": name, "text": text, "near_frame_cap": False,
            "final": {"sha256": hashlib.sha256(wav.read_bytes()).hexdigest()}}))

    def build(self, *extra):
        (self.tmp / "story.json").write_text(json.dumps(self.story))
        return run("build_video.py", str(self.tmp / "story.json"), "--audio-dir", str(self.audio),
                   "--output-dir", str(self.tmp / "out"), *extra)

    def test_build_and_verify_end_to_end(self):
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.tmp / "out/demo.manifest.json").read_text())
        self.assertEqual(sum(s["frames"] for s in manifest["scenes"]), manifest["frames"])
        self.assertEqual([c["id"] for c in manifest["audio"]], ["intro", "hello"])
        for clip, scene in zip(manifest["audio"], [manifest["scenes"][0], manifest["scenes"][1]]):
            self.assertEqual(clip["start_frame"], scene["start_frame"] + 18)
        verified = run("verify_video.py", str(self.tmp / "out/demo.manifest.json"))
        self.assertEqual(verified.returncode, 0, verified.stdout + verified.stderr)
        report = json.loads((self.tmp / "out/demo.manifest.verify.json").read_text())
        self.assertEqual(report["failed"], [])
        self.assertTrue(report["checks"]["format"]["ok"])

    def test_second_build_reuses_scenes_and_changed_narration_rerenders(self):
        self.build()
        first = (self.tmp / "out/demo/hello.mp4").stat().st_mtime_ns
        self.build()
        self.assertEqual((self.tmp / "out/demo/hello.mp4").stat().st_mtime_ns, first)
        self.write_clip("hello", self.story["scenes"][1]["narration"], 2.5)
        self.build()
        self.assertNotEqual((self.tmp / "out/demo/hello.mp4").stat().st_mtime_ns, first)

    def test_refuses_stale_or_truncated_narration(self):
        self.story["scenes"][1]["narration"] = "A different sentence now."
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no longer matches", result.stderr)
        self.story["scenes"][1]["narration"] = "First we print a greeting."
        metadata = self.audio / "hello-metadata.json"
        data = json.loads(metadata.read_text())
        data["near_frame_cap"] = True
        metadata.write_text(json.dumps(data))
        self.assertIn("truncated", self.build().stderr)

    def test_missing_marker_and_missing_audio_fail_clearly(self):
        self.story["scenes"][2]["marker"] = "Nope"
        self.assertIn("not in demo.cast", self.build().stderr)
        self.story["scenes"][2]["marker"] = "Count"
        (self.audio / "intro.wav").unlink()
        self.assertIn("missing narration for intro", self.build().stderr)

    def test_verify_detects_a_wrong_frame_count(self):
        self.build()
        path = self.tmp / "out/demo.manifest.json"
        manifest = json.loads(path.read_text())
        manifest["frames"] += 5
        path.write_text(json.dumps(manifest))
        self.assertEqual(run("verify_video.py", str(path)).returncode, 1)


if __name__ == "__main__":
    unittest.main()
