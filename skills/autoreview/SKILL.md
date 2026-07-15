---
name: autoreview
description: "Run structured code review as a closeout check on local, committed, branch, or PR changes before commit or ship. Use when the user asks for autoreview, Codex/Claude/Pi review, second-model review, or a final correctness and security pass after non-trivial code edits."
---

# Auto Review

Run the bundled structured review helper as a closeout check. This is code review, not Guardian `auto_review` approval routing.

Codex review is the default when no engine is set. It usually delivers the best closeout results and should remain the normal final-review engine. Unless the user explicitly selects an engine, model, or reasoning level, use `gpt-5.6-sol` with `max` reasoning; retry once with `gpt-5.6-terra` only when the account cannot access Sol. Claude and Pi remain opt-in.

For user-visible behavior, pair autoreview with `behavior-validator` when that skill is installed. Autoreview is source-aware and judges the change bundle; behavior validation is source-blind and judges the running product or tool against a behavior contract. A clean autoreview is not proof that a UI, CLI, API, or generated artifact works from the user's perspective.

Use when:

- user asks for Codex review / Claude review / Pi review / autoreview / second-model review
- after non-trivial code edits, before final/commit/ship
- reviewing a local branch or PR branch after fixes

## Contract

- Treat review output as advisory. Never blindly apply it.
- Verify every finding by reading the real code path and adjacent files.
- Read dependency docs/source/types when the finding depends on external behavior.
- Reject unrealistic edge cases, speculative risks, broad rewrites, and fixes that over-complicate the codebase.
- Prefer small fixes at the right ownership boundary; no refactor unless it clearly improves the bug class.
- When an accepted finding shows a bug class or repeated pattern, inspect the current PR scope for sibling instances before fixing.
- Fix the scoped bug class at once when practical; stop at touched surfaces, owner boundaries, and clear follow-up territory.
- Keep going until structured review returns no accepted/actionable findings only while the work remains inside the original task scope.
- If a review-triggered fix changes code, rerun focused tests and rerun the structured review helper.
- For security-audit suppression changes, verify accepted findings remain auditable: suppressed findings stay in structured output, active output keeps an unsuppressible suppression notice, and aggregate findings cannot hide unrelated active risk.
- Never switch or override a user-requested review engine, model, or reasoning level except for the documented Codex Sol-to-Terra account-access fallback. For capacity, rate-limit, and unrelated failures, retry the same command a few times with the same engine/model before reporting the failure.
- Be patient with large bundles. Structured review can take up to 30 minutes while the model call is active, especially with Codex tools or web search.
- Treat heartbeat lines like `review still running: ... elapsed=... pid=...` as healthy progress, not a hang. Let the helper continue while heartbeats are advancing. Pass `--stream-engine-output` when live engine text is useful; Codex and Claude filter tool/file chatter, other runnable engines pass raw output through.
- Do not kill a review just because it has been quiet for 2-5 minutes, or because it is still running under the 30-minute window. Inspect the process only after missing multiple expected heartbeats, after 30 minutes, or after an obviously failed subprocess; prefer letting the same helper command finish.
- Tools are useful in review mode. Codex receives the validated bundle in an empty workspace so ignored files and linked-worktree metadata remain unreadable; web search stays available for dependency contracts and upstream docs.
- Security perspective is always included, but it should not cripple legitimate functionality. Report security findings only when the change creates a concrete, actionable risk or removes an important safety check.
- Reviewer subprocesses preserve engine authentication and non-credentialed proxy variables needed by headless or restricted-network environments while stripping process-injection, Git override, and credentialed proxy values.
- Review bundles fail closed before engine invocation when tracked or untracked paths look sensitive or patch text looks secret-like. Safe large diffs are scanned in full, sent as one pass while they fit the aggregate prompt limit, then partitioned into complete bounded passes without truncation.
- For regression provenance, keep roles separate: blamed code author, blamed PR author, PR merger/committer, current PR author, and PR/date. If no blamed PR is traceable, use the blamed commit as the provenance: commit SHA, date, and author username. Do not guess a merger or frame missing PR metadata as a separate finding.
- If the blamed PR was merged by `clawsweeper[bot]` or another automation, identify the human trigger when practical. Check timeline/comments first; if rate-limited, use gitcrawl/cache or public PR HTML. Look for maintainer commands such as `@clawsweeper automerge`, `/landpr`, or labels/status comments that armed automerge. Report `automerge triggered by @login`; if not found, say trigger unknown.
- Do not invoke built-in `codex review`, nested reviewers, or reviewer panels from inside the review. The helper builds one validated bundle, calls the selected engine once for normal inputs or once per complete bounded chunk for oversized inputs, validates the structured results, and stops.
- Stop as soon as the helper exits 0 with no accepted/actionable findings. Do not run an extra review just to get a nicer "clean" line, a second opinion, or clearer closeout wording.
- Treat the helper's successful exit plus absence of actionable findings as the clean review result, even if the underlying Codex CLI output is terse.
- Multi-reviewer panels are opt-in only. Use them when explicitly requested or when risk justifies the extra spend; the main agent still verifies every accepted finding before fixing.
- If rejecting a finding as intentional/not worth fixing, add a brief inline code comment only when it explains a real invariant or ownership decision that future reviewers should know.
- If `gh`/Gitcrawl reports `database disk image is malformed`, run `gitcrawl doctor --json` once to let the portable cache repair before retrying review; do not bypass the shim unless repair fails and freshness requires live GitHub.
- If Gitcrawl reports a portable manifest mismatch, source/runtime DB health error, or stale portable-store checkout, run `gitcrawl doctor --json` and inspect `source_db_health`, `runtime_db_health`, and `portable_store_status` before falling back to live GitHub.
- Do not push just to review. Push only when the user requested push/ship/PR update.

## Scope Governor

Autoreview is a closeout gate, not permission to rewrite the task.

Before the first review, freeze a scope baseline: original request or issue, target branch, intended behavior, owner boundary, changed files, and non-test LOC. For inherited or already-bloated branches, use the intended PR diff as the baseline rather than accepting all existing branch drift.

Before patching a finding, classify it:

- **In-scope blocker**: the finding is introduced by the current diff, affects the same owner boundary, and can be fixed without changing the task's contract.
- **Follow-up**: the finding is real but belongs to an adjacent bug class, sibling surface, cleanup, or broader hardening track.
- **Stop-and-escalate**: the finding requires a new protocol/config/storage/public API contract, a different owner boundary, a release-process change, or a design choice outside the original request.

Stop patching and report the scope break instead of continuing when:

- a narrow PR turns into an architecture change, protocol change, migration, or release-process change;
- the diff grows past 2x the original files or non-test LOC without explicit approval to expand scope;
- two review-triggered patch cycles have not converged; pause and reclassify every remaining finding before another edit;
- the best fix is "define the canonical contract first" rather than another local inference layer;
- fixing the accepted finding would make the PR no longer describe the same behavior, issue, or owner boundary.

After the two-cycle pause, continue only when every remaining accepted finding is still an in-scope blocker. Otherwise preserve the useful analysis, identify the smallest safe landed subset if one exists, and open or request a follow-up for the larger fix. Do not keep committing speculative fixes just to satisfy the reviewer.

Do not stack or push review-triggered fix commits while scope classification or focused proof is unresolved. Keep exploratory edits local until the cycle is proven in scope; if scope breaks, remove them from the landing lane instead of preserving them as branch history.

Critical exceptions must be explicit: active data loss, crash, broken install/upgrade, release blocker, or concrete security exposure. If the exception is not one of those, it is not critical enough to blow up scope.

## Release Branches And Release Process

On release, beta, stable, hotfix, signing, notarization, appcast, package-publish, or release-check work, use freeze discipline even when the branch name is not release-like:

- Fix only release blockers, failed release infrastructure, exact backports, install/upgrade breakage, data loss, crashes, or concrete security exposure.
- Treat non-blocking autoreview findings as follow-ups for `main`, not reasons to broaden the release branch.
- Do not introduce new product behavior, config surface, protocol shape, migration, plugin ownership, docs narrative, or process policy unless it directly unblocks the release.
- Keep proof tied to the release target: exact branch/ref, failing check or shipped-risk reason, smallest command/proof, and whether the fix must also forward-port to `main`.
- If review discovers a real but non-critical design problem during release closeout, stop with a follow-up issue/PR plan; do not use the release branch as the refactor lane.

## Skill Path

Set the helper paths once. From this skills collection checkout:

```bash
export AUTOREVIEW="skills/autoreview/scripts/autoreview"
export AUTOREVIEW_HARNESS="skills/autoreview/scripts/test-review-harness"
```

For a global install, set `AGENTS_HOME` to the agent's skill root, then use `$AGENTS_HOME/skills/autoreview/scripts/autoreview`. For Codex this is commonly `${CODEX_HOME:-$HOME/.codex}`; for Claude Code it is commonly `$HOME/.claude`.

See [configuration and isolation](references/configuration-and-isolation.md#skill-path-set-once) for project-local paths, Windows examples, model overrides, and engine-specific requirements.

## Pick Target

Dirty local work:

```bash
"$AUTOREVIEW" --mode local
```

Use this only when the patch is actually unstaged/staged/untracked in the
current checkout. `--mode uncommitted` is accepted as an alias for `--mode local`.
For committed, pushed, or PR work, point the helper at the commit
or branch diff instead; do not force dirty modes just
because the helper docs mention dirty work first. A clean local review
only proves there is no local patch.

Branch/PR work:

```bash
"$AUTOREVIEW" --mode branch --base origin/main
```

Optional review context is first-class. Prompt files and datasets must be repo-relative so review bundles cannot pull arbitrary host files:

```bash
"$AUTOREVIEW" --mode branch --base origin/main --prompt-file review-notes.md --dataset evidence.json
```

If an open PR exists, use its actual base:

```bash
base=$(gh pr view --json baseRefName --jq .baseRefName)
"$AUTOREVIEW" --mode branch --base "origin/$base"
```

Committed single change:

```bash
"$AUTOREVIEW" --mode commit --commit HEAD
```

Use commit review for already-landed or already-pushed work on `main`. Reviewing
clean `main` against `origin/main` is usually an empty diff after push. For a
small stack, review each commit explicitly or review the branch before merging
with `--base`.

## Oversized Bundles

The helper scans the complete patch before partitioning it. Safe bundles stay in one integrated pass when they fit; larger bundles use complete bounded passes without truncation, and reports merge before exit-status checks. The run caps at eight passes, so split exceptionally large changes into coherent review targets.

Do not remove semantic artifacts such as lockfiles, generated clients, policies, manifests, or schemas merely to shrink the prompt. See [bundle handling details](references/configuration-and-isolation.md#oversized-bundles) for partition and location-preservation guarantees.

## Parallel Closeout

Format first if formatting can change line locations. Then tests and review may run in parallel:

```bash
"$AUTOREVIEW" --parallel-tests "<focused test command>"
```

Parallel tests run with a restricted environment and temporary home. Never place secrets in the command because it is printed before execution. If tests or review change code, rerun the affected tests and review until the final in-scope run is clean. See [parallel closeout isolation](references/configuration-and-isolation.md#parallel-closeout) for Windows shell selection and the optional trusted-maintainer credential staging path.

## Review Panels

Run multiple reviewers against one frozen bundle:

```bash
"$AUTOREVIEW" --reviewers codex,claude,pi
```

`--panel` is shorthand for Codex plus Claude unless `--engine` changes the first reviewer:

```bash
"$AUTOREVIEW" --panel
```

Set reviewer models and thinking/effort explicitly:

```bash
"$AUTOREVIEW" --reviewers codex,claude --model codex=gpt-5.6-sol --thinking codex=max --model claude=claude-fable-5 --thinking claude=max
```

Inline syntax is also supported for simple model IDs:

```bash
"$AUTOREVIEW" --reviewers codex:gpt-5.6-sol:max,claude:claude-fable-5:max
```

For models with slashes or extra colons, prefer keyed form:

```bash
"$AUTOREVIEW" --engine pi --model anthropic/claude-sonnet-4 --thinking high
"$AUTOREVIEW" --reviewers codex,pi --model codex=gpt-5.6-sol --model pi=anthropic/claude-sonnet-4
```

`--reviewers all` covers Codex, Claude, and Pi. Droid, Copilot, Cursor, and OpenCode selections fail closed because their current CLI contracts cannot confine project instructions, filesystem reads, or network fetches to the review boundary.

## Models and isolation

Codex defaults to `gpt-5.6-sol` with `max` reasoning and retries with `gpt-5.6-terra` only for an account-access failure. Explicit CLI values and `AUTOREVIEW_*` environment overrides always win. Claude defaults to `claude-fable-5`; Pi requires an explicit model. Droid, Copilot, Cursor, and OpenCode currently fail closed because their CLI contracts do not provide the required isolation.

Reviewers receive the validated bundle rather than unrestricted repository or host access. See [configuration and isolation](references/configuration-and-isolation.md) for all flags, environment variables, model tables, fallback behavior, and engine isolation details.

## Context Efficiency

Run the helper directly so target selection, engine choice, structured validation, and exit status all stay in one path. If output is noisy, summarize the completed helper output after it returns; do not ask another agent or reviewer to rerun the review.

## Helper

After setting `AUTOREVIEW` and `AUTOREVIEW_HARNESS` above:

```bash
"$AUTOREVIEW" --help
```

The smoke harness has thin shell wrappers over a shared Python implementation:

```bash
"$AUTOREVIEW_HARNESS" --fixture benign --engine codex
```

On native Windows, invoke the extensionless Python helper through Python:

```powershell
python $AUTOREVIEW --help
```

and the smoke harness:

```powershell
& $AUTOREVIEW_HARNESS -Fixture benign -Engine codex
```

The helper:

- selects dirty local changes first, then an open PR base, then `origin/main` for non-main branches; it never fetches automatically
- supports local, branch, and commit review plus repo-relative prompt files, datasets, panels, and parallel focused tests
- scans the complete patch for sensitive paths, secret-like content, unsupported binary/gitlink changes, and incomplete inputs before invoking a reviewer
- reviews one integrated bundle when possible and uses complete bounded passes for oversized safe changes
- isolates reviewer CLIs from repository-controlled configuration and host filesystem state
- prints heartbeats while long reviews are healthy, prints the exact clean marker on success, and exits nonzero for actionable findings

See [detailed helper capabilities](references/configuration-and-isolation.md#detailed-helper-capabilities) for the complete option and isolation contract.

## Final Report

Include:

- review command used
- tests/proof run
- findings accepted/rejected, briefly why
- the clean review result from the final helper/review run, or why a remaining finding was consciously rejected

Do not run another review solely to improve the final report wording. If the final helper run exited 0 and produced no accepted/actionable findings, report that exact run as clean.

## Credits

This skill is substantially based on the [`autoreview` skill from `openclaw/agent-skills`](https://github.com/openclaw/agent-skills/tree/main/skills/autoreview) and incorporates hardening and workflow improvements contributed by the OpenClaw maintainers and community. It is used and adapted under the MIT License; see [LICENSE](LICENSE) and [UPSTREAM.md](UPSTREAM.md).
