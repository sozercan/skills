# Skills

A small personal collection of agent skills. The layout is intentionally simple:

```text
skills/
└── <skill-name>/
    └── SKILL.md
```

Each skill is self-contained. There are no category folders under `skills/` unless a future skill genuinely needs extra supporting files.

## Available skills

| Skill | Purpose |
| --- | --- |
| [`a365-cli`](skills/a365-cli/SKILL.md) | Safe user-facing operation of the `a365` CLI for Microsoft 365 through agent365 MCP servers. |
| [`kusto-cli`](skills/kusto-cli/SKILL.md) | Safe user-facing operation of `kusto-cli` for Azure Data Explorer/Kusto terminal work. |

## Install locally

Copy or symlink the skill directories into your agent's skills directory.

```bash
# Copy one skill
cp -R skills/a365-cli ~/.agents/skills/

# Or copy all skills
cp -R skills/* ~/.agents/skills/
```

If your agent uses a different skills directory, copy `skills/<skill-name>` there instead. The important file is always `SKILL.md` at the root of the skill directory.

## Writing style

These skills are meant to be practical operator guides:

- user-facing, not implementation-facing
- task-oriented, with clear workflows and completion criteria
- safe by default, especially for commands that touch live services
- concise enough to load quickly
- examples use placeholders rather than real emails, IDs, tokens, tenant IDs, or customer data

## Add a skill

```bash
mkdir -p skills/my-skill
cat > skills/my-skill/SKILL.md <<'SKILL'
---
name: my-skill
description: Briefly states what this skill does. Use when the user asks for the concrete tasks this skill handles.
---

# My Skill

Describe the core workflow here.
SKILL
```

Keep the top-level `skills/` directory flat unless there is a strong reason to add more structure.
