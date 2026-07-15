# Upstream provenance

This skill merges:

- the local autoreview bundle previously installed under `~/.codex/skills/autoreview`, matching `openclaw/agent-skills` commit `48aef6ce6c1efde7ce9bdd0abc5400ad60506d4b` from June 2, 2026; and
- the hardened `skills/autoreview` implementation from `openclaw/agent-skills` at repository commit `3300b1086017741ad9bb5f00b9cceae4e7354f89` from July 14, 2026.

Intentional local differences:

- Codex defaults to `gpt-5.6-sol` with `max` reasoning when the user does not specify a model or reasoning level.
- User CLI and environment overrides keep precedence over built-in defaults.
- The skill description and closeout contract retain the local copy's explicit final-review positioning and same-model retry guidance.
- Installation examples cover the personal skills collection and Codex-global paths.
- Secondary model, path, and isolation details live in `references/configuration-and-isolation.md` so the main skill stays closer to the concise local copy.

The copied OpenClaw implementation is MIT-licensed; see `LICENSE`.
