# Skills

A small personal collection of agent skills. The layout is intentionally simple:

```text
skills/
└── <skill-name>/
    └── SKILL.md
```

Each skill is self-contained. There are no category folders under `skills/` unless a future skill genuinely needs extra supporting files.

Skills may include runtime support files such as `scripts/`. Non-runtime maintenance files live outside the install payload, for example in root-level `tests/` and `templates/`.

## Available skills

| Skill | Purpose |
| --- | --- |
| [`a365-cli`](skills/a365-cli/SKILL.md) | Safe user-facing operation of the `a365` CLI for Microsoft 365 through agent365 MCP servers. |
| [`kusto-cli`](skills/kusto-cli/SKILL.md) | Safe user-facing operation of `kusto-cli` for Azure Data Explorer/Kusto terminal work. |
| [`kindctl`](skills/kindctl/SKILL.md) | Repo/worktree-scoped kind cluster management. Installs only the skill docs and runtime `scripts/kindctl`; tests and templates stay outside the skill payload. |

## Install

Install all skills with the `skills` CLI:

```bash
npx skills@latest add sozercan/skills --all
```

List available skills without installing:

```bash
npx skills@latest add sozercan/skills --list
```

Install one skill:

```bash
npx skills@latest add sozercan/skills --skill a365-cli -y
npx skills@latest add sozercan/skills --skill kindctl -y
npx skills@latest add sozercan/skills --skill kusto-cli -y
```

Add `--global` to install globally instead of project-locally, or `--agent <name>` to target a specific supported agent.

## Writing style

These skills are meant to be practical operator guides:

- user-facing, not implementation-facing
- task-oriented, with clear workflows and completion criteria
- safe by default, especially for commands that touch live services
- concise enough to load quickly
- examples use placeholders rather than real emails, IDs, tokens, tenant IDs, or customer data

## Add a skill

Use the `skills` CLI initializer from the `skills/` directory:

```bash
cd skills
npx skills@latest init my-skill
```

Then edit `skills/my-skill/SKILL.md`. Keep the top-level `skills/` directory flat unless there is a strong reason to add more structure.
