---
name: ponytail-debt
description: "Harvest every `ponytail:` comment in the codebase into a debt ledger, so the deliberate shortcuts ponytail leaves behind get tracked instead of rotting into 'later means never'. Use when the user says 'ponytail debt', 'what did ponytail defer', 'list the shortcuts', 'ponytail ledger', or runs /ponytail-debt. One-shot report, changes nothing."
user_invocable: true
---

# Ponytail Debt

Every deliberate ponytail shortcut is marked with a `ponytail:` comment naming
its ceiling and upgrade path. This collects them into one ledger so a deferral
can't quietly become permanent.

When the user runs `/ponytail-debt`: scan, group, report. Changes nothing.

## Scan

Grep the repo for the comment marker, skipping caches, virtualenvs, and build
output:

```
grep -rnE '(#|//) ?ponytail:' . --exclude-dir={__pycache__,.venv,.pytest_cache,.git,node_modules,dist,build}
```

Each hit is one ledger row. The comment prefix keeps prose that merely mentions
the convention out of the ledger.

## Output

One row per marker, grouped by file:

`<file>:<line>, <what was simplified>. ceiling: <the limit named>. upgrade: <the trigger to revisit>.`

The convention is `ponytail: <ceiling>, <upgrade path>`, so pull the ceiling and
the trigger straight from the comment. Want an owner per row? add
`git blame -L<line>,<line>`.

Flag the rot risk: any `ponytail:` comment that names no upgrade path or trigger
gets a `no-trigger` tag — those are the ones that silently rot.

End with `<N> markers, <M> with no trigger.` Nothing found:
`No ponytail: debt. Clean ledger.`

## Boundaries

Reads and reports only, changes nothing. To persist it, ask and write the ledger
to a file (e.g. `PONYTAIL-DEBT.md`). One-shot.

---

*Adapted from [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) (MIT).*
