---
name: pr-prep
description: Prepare a pull request with verification, description, and checklist. Use when the user says 'prep a PR', 'open a PR', 'PR description'.
user_invocable: true
---
# Prepare Pull Request

When the user runs `/pr-prep`:

## Steps

1. **Run verification** — run the project's checks via `/verify`:
   - If any check fails → STOP and report

2. **Analyze changes**:
   - `git diff main...HEAD --stat` — list changed files
   - `git log main..HEAD --oneline` — list commits

3. **Tracker link** (when the repo has `tools/tracker`): find the issue you
   claimed — `python3 tools/tracker/tracker.py list --status in-progress` —
   and `show N` for its acceptance criteria. They go into the PR checklist
   verbatim; the body carries `Refs #N`. Never `Fixes`/`Closes`/`Resolves`:
   closing is the owner's protocol (`tracker owner done`), not GitHub's.

4. **Generate PR description**:

```markdown
## Summary
[1-3 bullet points from commit messages]

## Changes
[Group changes by area, using whatever areas fit the repo — e.g. API, UI, database, docs, config]

### [Area]
- [list changed files with brief description]

Refs #N

## Acceptance criteria (from the tracker issue)
- [ ] [copied verbatim from `tracker show N`]

## Checklist
- [ ] Tests: all passing (X tests, Y suites)
- [ ] Lint: no errors
- [ ] Build: compiles successfully
- [ ] Docs updated (if needed)
- [ ] No secrets in diff

## Test plan
[Describe how to verify the changes]

🤖 Generated with [Claude Code](https://claude.com/claude-code)
```

5. **Check docs**: check project docs (AGENTS.md/README) for sections needing updates, if present
6. **Open and hand over**: `gh pr create --title … --body-file <file>`; then, with the
   URL it printed, `python3 tools/tracker/tracker.py review N --pr <url>`
   (in-progress → review; refused if the head is not the claimed branch or the
   body lacks `Refs #N`) and post the /verify summary with
   `python3 tools/tracker/tracker.py note N "verify: <one line per check>"`.
   Without a tracker in the repo, stop at the ready-to-use PR body.
