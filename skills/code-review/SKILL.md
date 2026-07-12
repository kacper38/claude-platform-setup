---
name: code-review
description: "Automatically review changed code for bugs, security issues, and quality. TRIGGER proactively: after completing a significant code change (new feature, refactor, bug fix), OR when the user says 'review', 'check my code', 'look over this'. Do NOT trigger for trivial changes (typos, comments, config tweaks). Distinct from the built-in harness `code-review` skill (diff review at a given effort level) and from ponytail-review (over-engineering only)."
allowed-tools: [Read, Grep, Glob, Bash, Agent]
---

# Automatic Code Review

After a significant code change, review ALL modified files and report findings using the priority system below.

## Review Process

1. **Identify changed files** — use `git diff --name-only` (staged + unstaged)
2. **Read each changed file** — understand context, not just the diff
3. **Apply checks** from the checklist below
4. **Report findings** using the priority format

## Priority Levels

### BLOCKER — Must fix before commit
- Security vulnerabilities (injection, XSS, exposed secrets, missing auth)
- Data loss risk (missing tenant scoping (if multi-tenant), wrong DELETE cascade)
- Runtime crashes (undefined access, missing null checks on external data)
- Broken API contracts (wrong status codes, missing fields)

### SUGGESTION — Should fix, improves quality
- Missing error handling on external calls (DB, API, file I/O)
- Performance issues (N+1 queries, missing indexes, unnecessary re-renders)
- Missing input validation at system boundaries
- Code that's hard to understand without comments

### NIT — Optional, style/preference
- Naming improvements
- Unnecessary complexity that could be simplified
- Minor DRY violations (3+ identical lines)

## Checklist (language-agnostic)

- [ ] No hardcoded secrets, API keys, or passwords
- [ ] External input validated (user input, API responses, file reads)
- [ ] Error paths handled (try/catch on I/O, meaningful error messages)
- [ ] No unintended data exposure in API responses
- [ ] Resource cleanup (connections closed, listeners removed)
- [ ] Edge cases covered (empty arrays, null, 0, empty string)

## Output Format

```
## Code Review — [short summary]

### BLOCKER (X)
**[file:line] Issue title**
Why: explanation
Fix: concrete suggestion

### SUGGESTION (X)
**[file:line] Issue title**
Why: explanation

### NIT (X)
**[file:line] Issue title**

---
Verdict: APPROVE / NEEDS CHANGES (if any blockers)
```

## Rules

- Be specific — always include file path and line number
- Show the fix, not just the problem
- Don't flag things that are obviously intentional
- If no issues found, say "APPROVE — no issues found" (don't invent problems)
- Maximum 10 findings per review — focus on highest impact
