#!/usr/bin/env python3
"""Inspect and prepare asciinema v3 recordings for a narrated video.

  cast.py check   FILE [--scan-secrets] [--allow-nonzero-exit]
  cast.py markers FILE [--name Demo] [-o OUT]    turn sentinel escapes into marker events
  cast.py split   FILE --marker LABEL -o OUT     extract one chapter as its own cast

Standard library only. Recordings must be asciicast v3
(`asciinema convert -f asciicast-v3 in.cast out.cast` converts older ones).
"""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

SECRET_PATTERNS = {
    "github token": re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),
    "api key (sk-)": re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),
    "aws access key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "private key": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),
    "bearer token": re.compile(r"(?i)authorization:\s*bearer\s+[A-Za-z0-9._~+/=-]{16,}"),
}
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")


def fail(message):
    raise SystemExit("cast.py: " + message)


def sha256_file(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def read_cast(path):
    """Return (header, events); events are [interval, code, data] lists."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    if not lines:
        fail("empty recording: " + str(path))
    header = json.loads(lines[0])
    if header.get("version") != 3:
        fail(f"expected asciicast v3, got version {header.get('version')!r}; "
             "convert with: asciinema convert -f asciicast-v3 IN OUT")
    return header, [json.loads(line) for line in lines[1:] if line.strip()]


def write_cast(path, header, events):
    lines = [json.dumps(header, ensure_ascii=False)] + [json.dumps(e, ensure_ascii=False) for e in events]
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def exit_status(events):
    if events and events[-1][1] == "x":
        return events[-1][2]
    return None


def chapters(events):
    """Return {label: {first_event, last_event, start_seconds, seconds}} keyed by marker label."""
    marks = [(index, event[2]) for index, event in enumerate(events) if event[1] == "m"]
    elapsed, starts = 0.0, []
    for event in events:
        elapsed += event[0]
        starts.append(elapsed)
    total = elapsed
    result = {}
    for number, (index, label) in enumerate(marks):
        if label in result:
            fail("duplicate marker: " + label)
        stop = marks[number + 1][0] if number + 1 < len(marks) else len(events)
        # The trailing exit event is not part of the last chapter.
        while stop > index and events[stop - 1][1] == "x":
            stop -= 1
        end_time = starts[stop - 1] if stop > index else starts[index]
        result[label] = {"first_event": index, "last_event": stop - 1,
                         "start_seconds": round(starts[index], 3),
                         "seconds": round(end_time - starts[index], 3)}
    result_total = round(total, 3)
    return result, result_total


def command_check(args):
    header, events = read_cast(args.cast)
    status = exit_status(events)
    found, total = chapters(events)
    report = {
        "path": str(args.cast), "sha256": sha256_file(args.cast),
        "columns": header.get("term", {}).get("cols"), "rows": header.get("term", {}).get("rows"),
        "seconds": total, "exit_status": status,
        "markers": [{"label": label, **info} for label, info in found.items()],
    }
    problems = []
    if status is None:
        problems.append("recording has no exit event (was it interrupted?)")
    elif status != "0" and not args.allow_nonzero_exit:
        problems.append("recorded command exited with status " + status)
    if not found:
        problems.append("no chapter markers (see references/recording.md)")
    if args.scan_secrets:
        hits = []
        for index, event in enumerate(events):
            if event[1] not in ("o", "i"):
                continue
            text = ANSI.sub("", event[2])
            for name, pattern in SECRET_PATTERNS.items():
                if pattern.search(text):
                    hits.append({"event": index, "kind": name})
        report["secret_hits"] = hits
        if hits:
            problems.append(f"{len(hits)} possible secret(s) in the recording; re-record, do not redact by hand")
    report["problems"] = problems
    print(json.dumps(report, indent=2))
    return 1 if problems else 0


def rewrite_markers(events, name):
    sentinel = re.compile(r"\x1b\]1337;" + re.escape(name) + r"=([^\x07\x1b]*)\x07")
    out = []
    for event in events:
        if event[1] != "o" or (name + "=") not in event[2]:
            out.append(event)
            continue
        pending = event[0]
        for position, part in enumerate(sentinel.split(event[2])):
            if position % 2 == 0:
                if part:
                    out.append([pending, "o", part])
                    pending = 0.0
            else:
                out.append([pending, "m", part])
                pending = 0.0
    return out


def command_markers(args):
    header, events = read_cast(args.cast)
    rewritten = rewrite_markers(events, args.name)
    count = sum(1 for event in rewritten if event[1] == "m") - sum(1 for event in events if event[1] == "m")
    write_cast(args.output or args.cast, header, rewritten)
    print(f"{args.output or args.cast}: {count} marker(s) added")
    return 0 if count else 1


def chapter_cast(header, events, info):
    """Events for one chapter, after a screen reset, with all recorded output bytes kept."""
    body = events[info["first_event"] + 1:info["last_event"] + 1]  # skip the marker event itself
    out = [[0, "o", "\x1b[2J\x1b[H\x1b[?25l"]]
    for index, event in enumerate(body):
        out.append([0 if index == 0 else event[0], *event[1:]])
    out.append([0, "x", "0"])
    return out


def command_split(args):
    header, events = read_cast(args.cast)
    found, _ = chapters(events)
    if args.marker not in found:
        fail(f"no marker {args.marker!r}; have: " + ", ".join(found))
    write_cast(args.output, header, chapter_cast(header, events, found[args.marker]))
    print(args.output)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    check = sub.add_parser("check")
    check.add_argument("cast", type=Path)
    check.add_argument("--scan-secrets", action="store_true")
    check.add_argument("--allow-nonzero-exit", action="store_true")
    markers = sub.add_parser("markers")
    markers.add_argument("cast", type=Path)
    markers.add_argument("--name", default="DemoMarker")
    markers.add_argument("-o", "--output", type=Path)
    split = sub.add_parser("split")
    split.add_argument("cast", type=Path)
    split.add_argument("--marker", required=True)
    split.add_argument("-o", "--output", type=Path, required=True)
    args = parser.parse_args()
    handler = {"check": command_check, "markers": command_markers, "split": command_split}[args.command]
    sys.exit(handler(args))


if __name__ == "__main__":
    main()
