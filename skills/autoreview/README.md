# Autoreview

This directory vendors and minimally adapts the OpenClaw `autoreview` skill.

## Upstream

- Repository: [`openclaw/agent-skills`](https://github.com/openclaw/agent-skills)
- Source snapshot: [`skills/autoreview` at commit `3300b1086017741ad9bb5f00b9cceae4e7354f89`](https://github.com/openclaw/agent-skills/tree/3300b1086017741ad9bb5f00b9cceae4e7354f89/skills/autoreview)
- Commit: [`3300b1086017741ad9bb5f00b9cceae4e7354f89`](https://github.com/openclaw/agent-skills/commit/3300b1086017741ad9bb5f00b9cceae4e7354f89) (`fix(autoreview): restrict quoted credential keys (#99)`, July 14, 2026)

OpenClaw's work is used under the MIT License. The full notice is included below so single-skill installations retain it; the repository root also has [`LICENSE`](../../LICENSE).

## Local differences

- Codex defaults to `gpt-5.6-sol` with `max` reasoning instead of upstream's `high` reasoning.
- Non-runtime tests are kept in [`tests/autoreview`](../../tests/autoreview) so the installed skill payload contains only its documentation and runtime helpers.
- JVM-specific hardening tests skip when the host exposes a Java launcher but no usable Java runtime.
- Downstream hardening fixes cover review-input visibility, stable reviewed refs, unambiguous bundle serialization, and cross-platform UTF-8 handling.

## MIT License

Copyright (c) 2026 Sertac Ozercan

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
