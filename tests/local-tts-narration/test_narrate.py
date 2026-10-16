"""Tests for narrate.py against a fake OpenAI-style speech service."""

import importlib.util
import io
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import unittest
import wave
from http.server import BaseHTTPRequestHandler, HTTPServer

SCRIPT = Path(__file__).resolve().parents[2] / "skills/local-tts-narration/scripts/narrate.py"
spec = importlib.util.spec_from_file_location("narrate", SCRIPT)
narrate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(narrate)


def sine_wav(seconds, rate=24000):
    out = io.BytesIO()
    with wave.open(out, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(rate)
        audio.writeframes(b"".join(
            struct.pack("<h", int(8000 * math.sin(2 * math.pi * 220 * i / rate)))
            for i in range(int(seconds * rate))))
    return out.getvalue()


class FakeService(BaseHTTPRequestHandler):
    requests = []
    seconds_per_word = 0.3

    def log_message(self, *args):
        pass

    def do_GET(self):
        body = json.dumps({"data": [{"id": "qwen3-tts"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeService.requests.append(payload)
        wav = sine_wav(len(payload["input"].split()) * FakeService.seconds_per_word)
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(wav)))
        self.end_headers()
        self.wfile.write(wav)


@unittest.skipUnless(shutil.which("ffmpeg"), "ffmpeg is required")
class NarrateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), FakeService)
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.endpoint = f"http://127.0.0.1:{cls.server.server_port}/v1/audio/speech"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        FakeService.requests.clear()
        FakeService.seconds_per_word = 0.3
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.script = self.tmp / "script.json"
        self.script.write_text(json.dumps({"clips": [
            {"id": "intro", "text": "Welcome to the demo of this tool."},
            {"id": "result", "text": "The command finished and the output looks right."}]}))
        self.out = self.tmp / "audio"

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True, text=True)

    def generate(self, *extra):
        return self.run_cli("generate", "--script", str(self.script), "--output-dir", str(self.out),
                            "--endpoint", self.endpoint, *extra)

    def test_generates_normalized_clips_and_metadata(self):
        result = self.generate()
        self.assertEqual(result.returncode, 0, result.stderr)
        with wave.open(str(self.out / "intro.wav"), "rb") as audio:
            self.assertEqual((audio.getframerate(), audio.getnchannels(), audio.getsampwidth()), (48000, 1, 2))
        metadata = json.loads((self.out / "intro-metadata.json").read_text())
        self.assertEqual(metadata["text"], "Welcome to the demo of this tool.")
        self.assertFalse(metadata["near_frame_cap"])
        self.assertEqual(len(FakeService.requests), 2)

    def test_cache_hit_skips_the_service(self):
        self.generate()
        FakeService.requests.clear()
        self.assertEqual(self.generate().returncode, 0)
        self.assertEqual(FakeService.requests, [])

    def test_changed_reference_invalidates_the_cache(self):
        reference = self.tmp / "voice.wav"
        reference.write_bytes(sine_wav(1))
        self.generate("--reference-file", str(reference))
        FakeService.requests.clear()
        reference.write_bytes(sine_wav(2))
        self.generate("--reference-file", str(reference))
        self.assertEqual(len(FakeService.requests), 2)

    def test_changed_engine_id_invalidates_the_cache(self):
        self.generate("--engine-id", "image-a")
        FakeService.requests.clear()
        self.generate("--engine-id", "image-b")
        self.assertEqual(len(FakeService.requests), 2)

    def test_only_selected_clip_is_generated(self):
        self.generate("--clip", "result")
        self.assertEqual(len(FakeService.requests), 1)
        self.assertFalse((self.out / "intro.wav").exists())

    def test_flags_clip_that_hits_the_frame_cap(self):
        FakeService.seconds_per_word = 4  # 8 words -> 32 s, cap for 8 words is ~16 s
        self.script.write_text(json.dumps({"clips": [
            {"id": "long", "text": "one two three four five six seven eight", "max_frames": 160}]}))
        result = self.generate()
        self.assertEqual(result.returncode, 2)
        self.assertIn("truncation", result.stderr)

    def test_storyboard_scenes_and_plain_text_scripts(self):
        self.script.write_text(json.dumps({"scenes": [
            {"id": "card", "narration": "Hello."}, {"id": "silent", "title": "No narration"}]}))
        self.assertEqual([clip["id"] for clip in narrate.load_clips(self.script)], ["card"])
        text = self.tmp / "script.txt"
        text.write_text("First paragraph\nstill first.\n\nSecond paragraph.\n")
        clips = narrate.load_clips(text)
        self.assertEqual([clip["id"] for clip in clips], ["clip-01", "clip-02"])
        self.assertEqual(clips[0]["text"], "First paragraph still first.")

    def test_rejects_unsafe_and_duplicate_ids(self):
        self.script.write_text(json.dumps({"clips": [{"id": "../x", "text": "a"}]}))
        with self.assertRaises(SystemExit):
            narrate.load_clips(self.script)
        self.script.write_text(json.dumps({"clips": [{"id": "a", "text": "a"}, {"id": "a", "text": "b"}]}))
        with self.assertRaises(SystemExit):
            narrate.load_clips(self.script)

    def test_doctor_finds_the_model(self):
        result = self.run_cli("doctor", "--endpoint", self.endpoint)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["has_model"])

    def test_verify_reports_integrity_without_a_recognizer(self):
        self.generate()
        result = self.run_cli("verify", "--script", str(self.script), "--output-dir", str(self.out),
                              "--no-transcribe")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        summary = json.loads((self.out / "audio-qa/summary.json").read_text())
        self.assertEqual(summary["transcription"], "not performed")

    def test_verify_detects_changed_script_missing_clip_and_edited_audio(self):
        self.generate("--clip", "intro")
        self.script.write_text(json.dumps({"clips": [
            {"id": "intro", "text": "Different words now."},
            {"id": "result", "text": "Never generated."}]}))
        result = self.run_cli("verify", "--script", str(self.script), "--output-dir", str(self.out),
                              "--no-transcribe")
        self.assertEqual(result.returncode, 2)
        flags = {item["id"]: item["flags"] for item in
                 json.loads((self.out / "audio-qa/summary.json").read_text())["clips"]}
        self.assertEqual(flags["intro"], ["script_changed"])
        self.assertEqual(flags["result"], ["missing"])
        (self.out / "intro.wav").write_bytes(sine_wav(1))
        self.script.write_text(json.dumps({"clips": [{"id": "intro", "text": "Welcome to the demo of this tool."}]}))
        self.run_cli("verify", "--script", str(self.script), "--output-dir", str(self.out), "--no-transcribe")
        flags = json.loads((self.out / "audio-qa/intro.json").read_text())["flags"]
        self.assertIn("audio_changed", flags)

    def test_transcript_comparison(self):
        rate, flags = narrate.compare_transcript("There are twenty three clips.", "there are 23 clips")
        self.assertEqual((rate, flags), (0.0, []))
        rate, flags = narrate.compare_transcript("The deploy finished and every check passed cleanly.",
                                                 "The deploy finished and every")
        self.assertIn("check_ending", flags)
        self.assertIn("transcription_differs", flags)


if __name__ == "__main__":
    unittest.main()
