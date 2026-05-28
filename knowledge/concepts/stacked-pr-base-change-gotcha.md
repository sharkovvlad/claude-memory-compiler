---
title: "Stacked-PR base-change gotcha — merge goes into intermediate branch, not main"
aliases: [stacked-pr-base-change-gotcha, pr-base-rewrite-merge-target]
tags: [git, github, workflow, gotcha, multi-agent]
status: active
sources:
  - "daily/2026-05-28.md"
  - "concepts/release-protocol.md"
  - "concepts/migration-collision-guard.md"
created: 2026-05-28
updated: 2026-05-28
---

# Stacked-PR base-change gotcha

> 🔥 **HUB** — read before splitting a feature across ≥2 sequential
> migration PRs OR before using `gh pr api -X PATCH base=...` on any PR.

## TL;DR

If you change a PR's `base` from `main` to **another open branch** to
silence the migration-collision CI check, **GitHub's «Merge pull
request» button will merge into THAT base branch, not into main**.
Result: the merge looks successful (PR shows MERGED, gh CLI agrees), but
the commits never reach `origin/main`. Owner / next agent sees an
incomplete file-tree and has to recover.

## The incident (2026-05-28)

3-stage Stars Recurring feature:
* **#213** = Stage 1 (mig 364) → base `main` ✓
* **#214** = Stage 2 (mig 365 + Python) → base `main` initially, has
  migs 364+365 in diff (branched off #213)
* **#215** = Stage 3 (cancel Python) → base `main` initially, has
  migs 364+365 in diff (branched off #214)

CI's `pr-migration-collision.yml` flagged: «mig 364 in two open PRs»
(#213 and #214) and «mig 364+365 in two open PRs» (#214 and #215).

**Agent's mistake:** to clear the CI red status, agent ran
```bash
gh api -X PATCH repos/.../pulls/214 -f base=claude/stars-recurring-stage1-mig364
gh api -X PATCH repos/.../pulls/215 -f base=claude/stars-recurring-stage2-creation
```
Diffs went clean (#214 = only mig 365, #215 = only cancel Python), CI
went green.

**What happened next:**
1. Owner clicked Merge on #213 → mig 364 lands in `main`. ✓
2. Owner clicked Merge on #214. GitHub merges
   `claude/stars-recurring-stage2-creation` INTO
   `claude/stars-recurring-stage1-mig364` (its current base) — not
   into main. Branch gets the new commits; main stays untouched.
3. Owner clicked Merge on #215 → merged into stage2 branch.
4. **All three PRs show MERGED**, but `origin/main` is missing mig 365
   and Stage 3 Python.
5. Next migration-number lookup uses `main` as truth → picks `366` (wrong,
   stage2 branch already has `365`).
6. Discovered when owner reported «collision warning не уходит» on
   stale PR pages.

**Recovery:** open a new PR with `head=claude/stars-recurring-stage2-creation`
and `base=main`. The stage2 branch already contains both Stage 2 and
Stage 3 commits (because #215 merged into it), so one PR closes the gap.

## Why GitHub didn't auto-retarget

Other version-control hosts (e.g. Bitbucket) automatically retarget a
PR's base to `main` when the previous base branch is merged. **GitHub
does not.** A PR's `base` is set once and stays until manually changed
(or the branch is deleted, which sometimes auto-closes the PR but does
NOT auto-merge it to main).

Worse — when the base is a feature branch and the user merges, GitHub
DOES perform the merge into that feature branch. There is no warning
that this differs from merging to `main`.

## Two safe workflows for stacked migrations

### Option A — Sequential merge (preferred)

Don't touch bases. Accept the temporary CI red.

```
1. Open all PRs (#213, #214, #215) with base=main.
2. CI on #214/#215 will flag «collision» — that's OK, owner reads, ignores.
3. Owner merges #213.
4. Auto-deploy completes.
5. Owner clicks «Update branch» on #214 (GitHub UI button) →
   rebases off updated main → CI re-runs → migration #214's diff now
   excludes mig 364 → collision check passes → green.
6. Owner merges #214.
7. Repeat for #215.
```

Cost: owner has to click «Update branch» twice. Benefit: zero risk of
mis-targeted merge.

### Option B — Single combined PR

If all stages are inherently coupled (e.g. mig N defines an RPC that
Python in mig N+1 calls), put them in **one PR** with all migrations.
Pros: one merge, one deploy, one rollback unit. Cons: bigger review,
harder to bisect if regression.

Use the **80% rule:** if the stages can be merged independently with
each stage providing real user value, prefer Option A (3 PRs). If only
the last stage is user-visible (earlier stages are pure plumbing),
prefer Option B (1 PR).

### Option C (anti-pattern — do not use)

`gh api -X PATCH base=<feature-branch>`. The «just to make CI happy»
trap from the incident above. ONLY safe if:
* All downstream PRs will be merged via `gh api -X PUT .../merge` by
  an agent that knows to manually re-target before each merge, AND
* The agent also runs `git fetch origin <prev-stage-branch>` and
  rebases before each `pr merge`.

Effectively: don't do this without a fully scripted multi-merge
pipeline. Manual click-Merge with owner = guaranteed mis-target.

## Defensive coding for the agent

Before suggesting `gh api -X PATCH base=...` to any owner:

1. Ask: «Is this PR going to be merged by clicking the GitHub UI button
   later?» If yes → DON'T patch base. Use Option A.
2. If owner agrees to API-merge only → still verify before each merge:
   ```bash
   gh pr view <N> --json baseRefName
   # If baseRefName != "main" — STOP. Re-target first:
   gh api -X PATCH repos/.../pulls/<N> -f base=main
   # THEN merge.
   ```

## Recovery recipe (if you discover the gotcha after the fact)

Symptoms:
* `gh pr list` shows MERGED for stages 2/3.
* `git log origin/main` doesn't contain the expected commits.
* `git ls-tree origin/main migrations/` missing latest mig file.

Steps:
1. Find the branch that has all commits (usually the last stage's base
   branch, because each previous merge piled into it):
   ```bash
   git log origin/main..origin/<stage-N-branch> --oneline
   ```
2. Open recovery PR:
   ```bash
   gh pr create --head <stage-N-branch> --base main --title "..."
   ```
3. Verify diff vs main is exactly the missing changes:
   ```bash
   gh pr view <recovery-pr> --json files --jq '.files[].path'
   ```
4. Owner merges recovery PR.

In the 2026-05-28 incident this was PR #216 (stage2 branch → main).

## Cross-references

* `concepts/migration-collision-guard.md` — what the CI check does.
* `concepts/release-protocol.md` — overall PR-and-merge protocol.
* `daily/2026-05-28.md` — incident timeline.
* `concepts/stars-subscriptions-botfather-prereq.md` — sibling
  P0-incident from same session.
