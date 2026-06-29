#!/usr/bin/env python3
"""Fail if GitHub Actions workflow `uses:` references are not pinned to a full SHA."""
from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO_ROOT = HERE.parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
DOCKER_DIGEST_RE = re.compile(r"^docker://[^@]+@sha256:[0-9a-fA-F]{64}$")
USES_RE = re.compile(r"^\s*uses:\s*([^\s#]+)")

errors: list[str] = []
for path in sorted(WORKFLOWS.glob("*.yml")) + sorted(WORKFLOWS.glob("*.yaml")):
    for lineno, line in enumerate(path.read_text().splitlines(), 1):
        match = USES_RE.match(line)
        if not match:
            continue
        ref = match.group(1).strip('"\'')
        if ref.startswith("./"):
            continue
        if ref.startswith("docker://"):
            if not DOCKER_DIGEST_RE.fullmatch(ref):
                errors.append(f"{path}:{lineno}: docker action is not digest-pinned with @sha256:<digest>: {ref}")
            continue
        if "@" not in ref:
            errors.append(f"{path}:{lineno}: action is missing @sha: {ref}")
            continue
        action, version = ref.rsplit("@", 1)
        if not action or not SHA_RE.fullmatch(version):
            errors.append(f"{path}:{lineno}: action is not pinned to a 40-char SHA: {ref}")

if errors:
    print("GitHub Actions pinning errors:", file=sys.stderr)
    for error in errors:
        print(f"  - {error}", file=sys.stderr)
    sys.exit(1)

print("GitHub Actions uses references are pinned to SHAs")
