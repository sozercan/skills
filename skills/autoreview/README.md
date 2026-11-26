# Autoreview

This directory tracks the OpenClaw `autoreview` runtime with three narrow downstream behavior overrides.

## Upstream

- Repository: [`openclaw/agent-skills`](https://github.com/openclaw/agent-skills)
- Source snapshot: [`skills/autoreview` at commit `d6438c24de4220689ef2d9a40335328b2d6112e5`](https://github.com/openclaw/agent-skills/tree/d6438c24de4220689ef2d9a40335328b2d6112e5/skills/autoreview)
- Commit: [`d6438c24de4220689ef2d9a40335328b2d6112e5`](https://github.com/openclaw/agent-skills/commit/d6438c24de4220689ef2d9a40335328b2d6112e5)

The vendored runtime starts from that snapshot and carries only the behavior overrides below.
`AGENTS.md` records the downstream sync policy.

## Local differences

- Codex defaults to `gpt-6.2-sol` with `high` reasoning (with access-only fallback to `gpt-6.1-sol`) instead of upstream's `gpt-6.1-sol` at `medium` reasoning.
- Claude defaults to `claude-opus-5-5` with `high` reasoning (used only when explicitly requested or Codex is unavailable) instead of upstream's `claude-fable-5` default.
- Codex preserves `openai_base_url` from an external `CODEX_HOME/config.toml`, passes it through an internal OpenAI-compatible provider (`autoreview_openai_http`) with WebSocket transport disabled because isolated runs use `--ignore-user-config`, and excludes that internal provider from upstream's `command_auth` detection in `run_codex` so normal `auth.json`/keyring credentials and diagnostics remain intact.
- Non-generic upstream docs (`references/repository-entrypoint.md`, `references/openclaw.md`, and OpenClaw/ClawSweeper-specific sections in `SKILL.md` and `references/`) are omitted.

No other runtime behavior is intentionally changed.

## Packaging

The upstream test suites, fixtures, and optional `scripts/test-review-harness*` live-provider smoke wrappers are omitted. `scripts/autoreview` does not depend on them. A small downstream test covers only the three local behavior overrides.

## Upstream license

OpenClaw's work is used under the MIT License:

```text
MIT License

Copyright (c) 2026 openclaw

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
