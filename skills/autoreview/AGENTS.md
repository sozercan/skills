# Autoreview Skill

- Canonical source: `openclaw/agent-skills`, under `skills/autoreview`.
- Before editing any copy, fast-forward a checkout of `openclaw/agent-skills` from `origin/main`.
- Make and validate shared changes in canonical `skills/autoreview` first, then sync the complete directory into downstream repos.
- Never create repo-local behavior variants; downstream differences belong in repo-level validation, not the skill.
- Narrow downstream exception in this repository: preserve `openai_base_url` from `CODEX_HOME/config.toml` while Codex user config is otherwise ignored.
