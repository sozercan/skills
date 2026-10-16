#!/usr/bin/env python3
"""Build a narrated 1920x1080, 30 fps MP4 from a storyboard, an asciinema cast and narration clips.

  build_video.py STORYBOARD --audio-dir DIR --output-dir DIR

Needs: ffmpeg + ffprobe, agg (asciinema gif generator), Python Pillow.
Narration clips come from local-tts-narration's narrate.py (`<id>.wav` and
`<id>-metadata.json` per scene). See references/storyboard.md for the format.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import wave

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cast as castlib  # noqa: E402

WIDTH, HEIGHT, FPS = 1920, 1080, 30
AUDIO_RATE = 48000
SAMPLES_PER_FRAME = AUDIO_RATE // FPS
LEAD_FRAMES = 18          # silence before narration starts in a scene
TAIL_FRAMES = 54          # time after narration ends before the next scene
HOLD_SECONDS = 1.2        # how long a finished terminal stays on screen
TERMINAL_BOX = (1752, 868)
TERMINAL_Y = 154
DEFAULT_THEME = {"background": "#1c1e20", "foreground": "#f4f2ec", "muted": "#b1b4ba", "accent": "#e8a1ee"}
SANS = ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf"]
SANS_BOLD = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf",
             "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf",
             "C:/Windows/Fonts/arialbd.ttf"]
MONO = ["/System/Library/Fonts/Menlo.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/dejavu/DejaVuSansMono.ttf", "C:/Windows/Fonts/consola.ttf"]


def require(condition, message):
    if not condition:
        raise SystemExit("build_video.py: " + message)


def digest(path):
    return castlib.sha256_file(path)


def run(command):
    result = subprocess.run(command, capture_output=True, text=True)
    require(result.returncode == 0, f"{command[0]} failed: {result.stderr[-3000:]}")
    return result.stdout


def probe(path):
    return json.loads(run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)]))


# --- storyboard -----------------------------------------------------------

def load_storyboard(path):
    path = Path(path).resolve()
    story = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(story.get("scenes"), list) and story["scenes"], "storyboard needs a non-empty 'scenes' list")
    seen = set()
    for scene in story["scenes"]:
        name = scene.get("id")
        require(isinstance(name, str) and re.fullmatch(r"[a-z0-9-]+", name), f"scene id must match [a-z0-9-]+: {name!r}")
        require(name not in seen, "duplicate scene id: " + name)
        seen.add(name)
        require(scene.get("type") in ("card", "chapter"), f"scene {name}: type must be 'card' or 'chapter'")
        if scene["type"] == "chapter":
            require(scene.get("marker"), f"scene {name}: chapter needs a 'marker'")
            require(scene.get("cast") or story.get("cast"), f"scene {name}: no cast (set 'cast' on the scene or storyboard)")
            speed = scene.get("max_speed", 2)
            require(isinstance(speed, (int, float)) and not isinstance(speed, bool) and 1 <= speed <= 4,
                    f"scene {name}: max_speed must be between 1 and 4")
    story["_dir"] = path.parent
    story["theme"] = {**DEFAULT_THEME, **story.get("theme", {})}
    return story


def cast_path(story, scene):
    return (story["_dir"] / (scene.get("cast") or story["cast"])).resolve()


# --- narration ------------------------------------------------------------

def load_narration(scene, audio_dir):
    """Return None for a silent scene, else details of its validated clip."""
    text = scene.get("narration")
    if not text:
        return None
    clip_id = scene["id"]
    wav, metadata_path = audio_dir / f"{clip_id}.wav", audio_dir / f"{clip_id}-metadata.json"
    require(wav.is_file() and metadata_path.is_file(), f"missing narration for {clip_id}; run narrate.py generate")
    metadata = json.loads(metadata_path.read_text())
    require(metadata["text"] == " ".join(str(text).split()), f"narration for {clip_id} no longer matches the storyboard")
    require(not metadata["near_frame_cap"], f"narration for {clip_id} may be truncated (frame cap)")
    require(digest(wav) == metadata["final"]["sha256"], f"audio for {clip_id} changed since it was generated")
    with wave.open(str(wav), "rb") as audio:
        require((audio.getframerate(), audio.getnchannels(), audio.getsampwidth()) == (AUDIO_RATE, 1, 2),
                f"narration for {clip_id} must be 48 kHz mono PCM16")
        samples = audio.getnframes()
    return {"path": wav, "sha256": digest(wav), "samples": samples,
            "frames": math.ceil(samples / SAMPLES_PER_FRAME)}


# --- drawing --------------------------------------------------------------

def find_font(override, candidates):
    for candidate in ([override] if override else []) + candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    return None


class Painter:
    def __init__(self, story, args):
        try:
            from PIL import Image, ImageDraw, ImageFont
        except ImportError:
            raise SystemExit("build_video.py: Pillow is required (pip install pillow)")
        self.Image, self.ImageDraw, self.ImageFont = Image, ImageDraw, ImageFont
        self.theme = story["theme"]
        self.sans = find_font(args.font, SANS)
        self.bold = find_font(args.bold_font, SANS_BOLD) or self.sans
        self.mono = find_font(args.mono_font, MONO)

    def font(self, size, bold=False, mono=False):
        path = self.mono if mono else self.bold if bold else self.sans
        if path:
            return self.ImageFont.truetype(path, size)
        return self.ImageFont.load_default(size)

    def text(self, draw, xy, value, size, color, bold=False, mono=False):
        font = self.font(size, bold, mono)
        box = draw.textbbox(xy, value, font=font, anchor="lt")
        require(box[2] <= WIDTH - 70 and box[3] <= HEIGHT - 25, "text does not fit the frame: " + value)
        draw.text(xy, value, font=font, fill=color, anchor="lt")

    def wrapped(self, draw, xy, value, size, color, width=1640, bold=False):
        font = self.font(size, bold)
        rows, row = [], ""
        for word in value.split():
            candidate = (row + " " + word).strip()
            if row and draw.textlength(candidate, font=font) > width:
                rows.append(row)
                row = word
            else:
                row = candidate
        rows.append(row)
        for index, line in enumerate(rows):
            self.text(draw, (xy[0], xy[1] + index * round(size * 1.2)), line, size, color, bold)
        return xy[1] + len(rows) * round(size * 1.2)

    def card(self, story, scene, index, total, output):
        t = self.theme
        image = self.Image.new("RGB", (WIDTH, HEIGHT), t["background"])
        draw = self.ImageDraw.Draw(image)
        label = story.get("label", "")
        if label:
            self.text(draw, (134, 94), label, 27, t["accent"], mono=True)
        draw.line((134, 166, 1786, 166), fill="#45474c", width=2)
        bottom = self.wrapped(draw, (134, 254), scene["title"], 91, t["foreground"], bold=True)
        if scene.get("subtitle"):
            bottom = self.wrapped(draw, (139, bottom + 64), scene["subtitle"], 49, t["muted"], width=1550)
        if scene.get("link"):
            self.text(draw, (139, max(bottom + 90, 800)), scene["link"], 43, t["foreground"], mono=True)
        image.save(output)

    def chrome(self, story, scene, number, total, output):
        t = self.theme
        image = self.Image.new("RGB", (WIDTH, HEIGHT), t["background"])
        draw = self.ImageDraw.Draw(image)
        label = story.get("label", "")
        self.text(draw, (84, 19), f"{label}  /  {number:02d} OF {total:02d}".strip(" /"), 19, t["accent"], mono=True)
        self.text(draw, (84, 51), scene.get("title", scene["marker"]), 43, t["foreground"], bold=True)
        if scene.get("cue"):
            self.text(draw, (84, 109), scene["cue"], 26, t["muted"])
        self.text(draw, (84, 1036), story.get("footer_left", "Recorded execution  |  Waiting time compressed"),
                  19, t["muted"])
        if story.get("footer_right"):
            font = self.font(19)
            width = draw.textlength(story["footer_right"], font=font)
            self.text(draw, (int(WIDTH - 84 - width), 1036), story["footer_right"], 19, t["muted"])
        image.save(output)


# --- video ----------------------------------------------------------------

def encode(image, output, frames, terminal=None, factor=1.0):
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]
    if terminal:
        info = probe(terminal)["streams"][0]
        scale = min(TERMINAL_BOX[0] / info["width"], TERMINAL_BOX[1] / info["height"])
        width, height = (int(info[key] * scale) // 2 * 2 for key in ("width", "height"))
        x = (WIDTH - width) // 2
        command += ["-ignore_loop", "1", "-i", str(terminal), "-loop", "1", "-framerate", str(FPS), "-i", str(image),
                    "-filter_complex",
                    f"[0:v]setpts={factor:.9f}*(PTS-STARTPTS),scale={width}:{height}:flags=lanczos,fps={FPS}[term];"
                    f"[1:v][term]overlay={x}:{TERMINAL_Y}:shortest=1,tpad=stop_mode=clone:stop_duration=600[video]",
                    "-map", "[video]"]
    else:
        command += ["-loop", "1", "-framerate", str(FPS), "-i", str(image), "-vf", "fade=t=in:st=0:d=0.3"]
    command += ["-an", "-c:v", "libx264", "-crf", "17", "-preset", "fast", "-pix_fmt", "yuv420p", "-r", str(FPS),
                "-frames:v", str(frames), "-movflags", "+faststart", str(output)]
    run(command)
    stream = probe(output)["streams"][0]
    require(int(stream["nb_frames"]) == frames, f"scene frame count mismatch for {output}")
    require((stream["width"], stream["height"]) == (WIDTH, HEIGHT), f"scene size mismatch for {output}")


def agg_font_size(columns, rows):
    return max(12, min(40, int(min(TERMINAL_BOX[0] / (columns * 0.6), TERMINAL_BOX[1] / (rows * 1.1)))))


def render_scene(story, painter, scene, index, count, narration, work, args, chapters_cache):
    """Render one scene video and return its provenance record (cached by input hash)."""
    scene_id = scene["id"]
    output, picture, report_path = work / f"{scene_id}.mp4", work / f"{scene_id}.png", work / f"{scene_id}.json"
    source = cast_path(story, scene) if scene["type"] == "chapter" else None
    inputs = {"scene": scene, "theme": story["theme"], "label": story.get("label"),
              "footer": [story.get("footer_left"), story.get("footer_right")],
              "narration_sha256": narration["sha256"] if narration else None,
              "cast_sha256": digest(source) if source else None,
              "tool_sha256": digest(__file__), "fonts": [painter.sans, painter.bold, painter.mono],
              "agg_font_family": args.agg_font_family}
    narration_frames = narration["frames"] if narration else 0
    if report_path.exists() and output.is_file() and not args.force:
        report = json.loads(report_path.read_text())
        if report.get("inputs") == inputs and digest(output) == report["video_sha256"]:
            return report
    terminal, factor, chapter_info = None, 1.0, None
    if scene["type"] == "card":
        hold = scene.get("hold_seconds", 3)
        frames = round(hold * FPS)
        if narration:
            frames = max(frames, LEAD_FRAMES + narration_frames + TAIL_FRAMES)
        painter.card(story, scene, index, count, picture)
    else:
        header, events, found = chapters_cache(source)
        chapter_info = found[scene["marker"]] if scene["marker"] in found else None
        require(chapter_info, f"scene {scene_id}: marker {scene['marker']!r} not in {source.name}; have: "
                              + ", ".join(found))
        split = work / f"{scene_id}.cast"
        castlib.write_cast(split, header, castlib.chapter_cast(header, events, chapter_info))
        terminal = work / f"{scene_id}.gif"
        columns, rows = header.get("term", {}).get("cols", 100), header.get("term", {}).get("rows", 28)
        command = ["agg", str(split), str(terminal), "--font-size", str(agg_font_size(columns, rows)),
                   "--line-height", "1.1", "--theme", scene.get("theme", "monokai"), "--idle-time-limit", "2",
                   "--last-frame-duration", "1.2", "--fps-cap", str(FPS), "--no-loop", "--quiet"]
        if args.agg_font_family:
            command += ["--font-family", args.agg_font_family]
        run(command)
        duration = float(probe(terminal)["format"]["duration"])
        max_speed = scene.get("max_speed", 2)
        seconds = max((LEAD_FRAMES + narration_frames + TAIL_FRAMES) / FPS if narration else 0,
                      min(duration + HOLD_SECONDS, 40), duration / max_speed + HOLD_SECONDS)
        frames = math.ceil(seconds * FPS)
        factor = min(1.0, (frames / FPS - HOLD_SECONDS) / duration)
        painter.chrome(story, scene, chapter_number(story, scene), chapter_total(story), picture)
    encode(picture, output, frames, terminal, factor)
    report = {"id": scene_id, "frames": frames, "inputs": inputs, "video_sha256": digest(output),
              "playback_speed": round(1 / factor, 3),
              "source_events": ({"first_event": chapter_info["first_event"], "last_event": chapter_info["last_event"]}
                                if chapter_info else None)}
    report_path.write_text(json.dumps(report, indent=2) + "\n")
    return report


def chapter_number(story, scene):
    return [s["id"] for s in story["scenes"] if s["type"] == "chapter"].index(scene["id"]) + 1


def chapter_total(story):
    return sum(1 for s in story["scenes"] if s["type"] == "chapter")


def write_audio_track(path, placements, total_frames):
    """One 48 kHz mono PCM16 track exactly as long as the video, with clips at their sample offsets."""
    total = total_frames * SAMPLES_PER_FRAME
    cursor = 0
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(AUDIO_RATE)
        for placement in placements:
            start = placement["start_sample"]
            require(start >= cursor, f"narration overlaps in scene {placement['id']}")
            out.writeframes(b"\0\0" * (start - cursor))
            with wave.open(str(placement["path"]), "rb") as clip:
                data = clip.readframes(clip.getnframes())
            require(start + len(data) // 2 <= total, f"narration for {placement['id']} runs past the video")
            out.writeframes(data)
            cursor = start + len(data) // 2
        out.writeframes(b"\0\0" * (total - cursor))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("storyboard", type=Path)
    parser.add_argument("--audio-dir", type=Path, required=True, help="narrate.py output directory")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--name", help="output basename (default: storyboard 'output' or its filename)")
    parser.add_argument("--jobs", type=int, default=2, help="scenes rendered in parallel (1-4)")
    parser.add_argument("--force", action="store_true", help="ignore cached scene renders")
    parser.add_argument("--font", help="sans font file for titles")
    parser.add_argument("--bold-font", help="bold sans font file for titles")
    parser.add_argument("--mono-font", help="monospace font file for labels and links")
    parser.add_argument("--agg-font-family", help="terminal font families for agg, comma separated")
    args = parser.parse_args()
    require(1 <= args.jobs <= 4, "--jobs must be 1 to 4")
    for tool in ("ffmpeg", "ffprobe", "agg"):
        require(shutil.which(tool), f"{tool} is required but not on PATH")

    story = load_storyboard(args.storyboard)
    name = args.name or story.get("output") or args.storyboard.stem
    args.output_dir = args.output_dir.resolve()
    work = args.output_dir / name
    work.mkdir(parents=True, exist_ok=True)
    painter = Painter(story, args)

    parsed = {}

    def chapters_cache(path):
        if path not in parsed:
            header, events = castlib.read_cast(path)
            parsed[path] = (header, events, castlib.chapters(events)[0])
            status = castlib.exit_status(events)
            require(status == "0", f"{path.name} did not exit successfully (status {status!r})")
        return parsed[path]

    scenes = story["scenes"]
    narrations = [load_narration(scene, args.audio_dir.resolve()) for scene in scenes]
    for scene in scenes:
        if scene["type"] == "chapter":
            chapters_cache(cast_path(story, scene))  # parse once, serially
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(render_scene, story, painter, scene, index, len(scenes), narrations[index],
                               work, args, chapters_cache) for index, scene in enumerate(scenes)]
        reports = [future.result() for future in futures]

    offset, placements, manifest_scenes = 0, [], []
    for scene, narration, report in zip(scenes, narrations, reports):
        if narration:
            placements.append({"id": scene["id"], "path": narration["path"], "sha256": narration["sha256"],
                               "start_frame": offset + LEAD_FRAMES, "start_sample": (offset + LEAD_FRAMES) * SAMPLES_PER_FRAME,
                               "samples": narration["samples"]})
        manifest_scenes.append({"id": scene["id"], "type": scene["type"], "start_frame": offset,
                                "frames": report["frames"], "video": str(work / f"{scene['id']}.mp4"),
                                "playback_speed": report["playback_speed"]})
        offset += report["frames"]
    audio_track = work / "narration.wav"
    write_audio_track(audio_track, placements, offset)

    listing = work / "scenes.txt"
    listing.write_text("".join(f"file '{item['video']}'\n" for item in manifest_scenes))
    final = args.output_dir / f"{name}.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-f", "concat", "-safe", "0",
         "-i", str(listing), "-i", str(audio_track), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(final)])
    manifest = {
        "video": str(final), "video_sha256": digest(final), "frames": offset, "fps": FPS,
        "size": [WIDTH, HEIGHT], "seconds": round(offset / FPS, 3),
        "sources": sorted({str(cast_path(story, s)) for s in scenes if s["type"] == "chapter"}),
        "narration_track": str(audio_track),
        "scenes": manifest_scenes,
        "audio": [{"id": p["id"], "path": str(p["path"]), "sha256": p["sha256"], "start_frame": p["start_frame"],
                   "start_sample": p["start_sample"], "samples": p["samples"]} for p in placements],
    }
    (args.output_dir / f"{name}.manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"video": str(final), "seconds": manifest["seconds"], "scenes": len(scenes)}))


if __name__ == "__main__":
    main()
