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

3. **Generate PR description**:

```markdown
## Summary
[1-3 bullet points from commit messages]

## Changes
[Group changes by area, using whatever areas fit the repo — e.g. API, UI, database, docs, config]

### [Area]
- [list changed files with brief description]

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

4. **Check docs**: check project docs (CLAUDE.md/README) for sections needing updates, if present
5. **Output**: Ready-to-use PR body for `gh pr create`
