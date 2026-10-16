# Recording a demo

## Terminal

Use a fixed, modest size so text stays legible after scaling to 1080p: about 100 columns by 28 rows. Wider terminals are scaled down and read smaller. Use a clean prompt, no personal paths or hostnames, and a readable dark or light theme.

## Make the demo scriptable

A shell script that prints each step is easier to re-record than a live session. Typical shape:

```sh
#!/usr/bin/env bash
marker() { printf '\e]1337;DemoMarker=%s\a' "$1"; }   # chapter boundary
say()    { printf '\n# %s\n' "$*"; sleep 1; }          # visible comment, optional
run()    { printf '$ %s\n' "$*"; sleep 0.6; eval "$@"; sleep 1; }

marker "1 - Install"
say "Install the tool"
run brew install example/tap/tool

marker "2 - First run"
run tool init demo
run tool status
```

- Print the command before running it so the viewer sees what was typed. Simulated typing is fine if the command and output are real.
- Put a `marker` at the start of every chapter. Labels must be unique and are matched exactly by the storyboard.
- `sleep` between steps so output is readable; the build step compresses long idle waits (more than 2 seconds) but cannot add readable time.
- Keep installation, image builds, and credential setup out of the recording. Set them up beforehand.
- Use only targets and accounts you are authorized to use, and sanitize output at the source (select fields) instead of hoping to edit it later.

## Record

```sh
asciinema rec --overwrite --cols 100 --rows 28 --idle-time-limit 2 \
  --command "bash demo.sh" demo.cast
python3 "$HOME/.agents/skills/terminal-demo-video/scripts/cast.py" markers demo.cast
python3 "$HOME/.agents/skills/terminal-demo-video/scripts/cast.py" check demo.cast --scan-secrets
```

asciinema 3.x writes asciicast v3. Terminals swallow the marker escape, but asciinema records it; `cast.py markers` rewrites each one into a proper marker event and removes it from the output stream. Use `--name` if you used a different sentinel (`ESC ] 1337 ; NAME = label BEL`).

If the demo needs a live system, check that it is healthy first and record against exactly the target you were told to use. Re-recording overwrites output, so copy an accepted `demo.cast` (and note its `sha256` from `cast.py check`) before recording again.

## Acceptance

Accept a recording only when all of these hold: exit status 0 (or an intentional failure you narrate), every expected chapter present, the outcome on screen is the one you will describe, the secret scan is clean and you have read the output, and values you will quote (counts, timings, costs) are on screen. For measured comparisons, keep the workloads comparable, compute percentages from unrounded values, and show a slower or failed path if it matters to the conclusion.
