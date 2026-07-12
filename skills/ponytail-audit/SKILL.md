---
name: ponytail-audit
description: "Whole-repo audit for over-engineering — like ponytail-review but scans the entire codebase instead of a diff: a ranked list of what to delete, simplify, or replace with stdlib/native equivalents. Use when the user says 'audit for over-engineering', 'where is the bloat', 'what can we simplify repo-wide', or runs /ponytail-audit. Analysis only, applies nothing."
user_invocable: true
arg_description: "[path] (optional — narrows the audit to a subtree)"
---

# Ponytail Audit

Whole-repo audit for over-engineering. Like `ponytail-review`, but scans the
entire codebase (or the given `[path]`) instead of a single diff. Produces a
ranked, one-shot report of what to delete, simplify, or replace — does **not**
apply fixes.

When the user runs `/ponytail-audit [path]`: sweep the source tree (skip
`__pycache__`, `.venv`, `.pytest_cache`, `.git`, `.mypy_cache`, `.ruff_cache`,
`node_modules`, `dist`, `build`, `.next`, `coverage`, `target`,
build output), rank findings by impact (lines + deps removable), and report.

## Format

Per finding, ranked by impact:

`<tag> <what to cut>. <replacement>. [<path>:L<line>]`

### Tags (same as ponytail-review)

- `delete:` dead code, unused flexibility, speculative feature.
- `stdlib:` hand-rolled thing the standard library ships (Python: `json`, `itertools`, `functools`, `collections`; JS/TS: `URL`, `Intl`, `structuredClone`, Array methods).
- `native:` dependency or code doing what the language already does (Python: `@dataclass`, comprehension, context manager, `str` methods; TS/JS: object literal + `Record`, `.map()`/`.filter()`, template literals, optional chaining).
- `yagni:` abstraction with one implementation, config nobody sets, layer with one caller.
- `shrink:` same logic, fewer lines.

Group the biggest wins first (whole modules/deps removable), then file-level
cuts. A single unused dependency in `pyproject.toml`/`requirements.txt`/`package.json`
outranks ten one-line shrinks.

## Scoring

End with: `net: -<N> lines, -<M> deps possible.`

If the repo is already lean: `Lean already. Nothing worth cutting.` and stop.

## Boundaries

Scope: over-engineering and complexity only. Correctness bugs, security
holes, and performance issues are **out of scope** — route them to the
`code-reviewer` agent. One-shot report; reads and ranks,
changes nothing. To persist it, ask and write to e.g. `PONYTAIL-AUDIT.md`.

---

*Adapted from [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) (MIT).*
