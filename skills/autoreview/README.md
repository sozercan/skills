# Autoreview

This directory vendors and minimally adapts the OpenClaw `autoreview` skill.

## Upstream

- Repository: [`openclaw/agent-skills`](https://github.com/openclaw/agent-skills)
- Source snapshot: [`skills/autoreview` at commit `3300b1086017741ad9bb5f00b9cceae4e7354f89`](https://github.com/openclaw/agent-skills/tree/3300b1086017741ad9bb5f00b9cceae4e7354f89/skills/autoreview)
- Commit: [`3300b1086017741ad9bb5f00b9cceae4e7354f89`](https://github.com/openclaw/agent-skills/commit/3300b1086017741ad9bb5f00b9cceae4e7354f89) (`fix(autoreview): restrict quoted credential keys (#99)`, July 14, 2026)

OpenClaw's work is used under the MIT License. Its copyright notice is preserved in the repository-root [`LICENSE`](../../LICENSE).

## Local differences

- Codex defaults to `gpt-5.6-sol` with `max` reasoning instead of upstream's `high` reasoning.
- Non-runtime tests are kept in [`tests/autoreview`](../../tests/autoreview) so the installed skill payload contains only its documentation and runtime helpers.
- JVM-specific hardening tests skip when the host exposes a Java launcher but no usable Java runtime.
- Downstream hardening fixes cover review-input visibility, stable reviewed refs, unambiguous bundle serialization, and cross-platform UTF-8 handling.
