---
name: ponytail-review
description: "Code review focused exclusively on over-engineering — finds what to DELETE in the current git diff: reinvented stdlib, unneeded deps, speculative abstractions, dead flexibility. Use when the user says 'review for over-engineering', 'what can we delete', 'is this over-engineered', 'simplify review', or runs /ponytail-review. Complements (does not replace) correctness/security review."
user_invocable: true
---

# Ponytail Review

Review the current diff for unnecessary complexity. One line per finding:
location, what to cut, what replaces it. The diff's best outcome is getting
shorter.

When the user runs `/ponytail-review`: review the working diff (`git diff`, or
`git diff main...HEAD` for a branch). List findings only — do **not** apply
fixes.

## Format

`L<line>: <tag> <what>. <replacement>.` — or `<file>:L<line>: …` for multi-file diffs.

### Tags

- `delete:` dead code, unused flexibility, speculative feature. Replacement: nothing.
- `stdlib:` hand-rolled thing the standard library ships. Name the function.
- `native:` dependency or code doing what the language already does. Name the feature.
- `yagni:` abstraction with one implementation, config nobody sets, layer with one caller.
- `shrink:` same logic, fewer lines. Show the shorter form.

## Examples

✅ `L12-38: stdlib: 27-line hand-rolled config parser. json.loads + a dict lookup, done.`

✅ `L4: native: lodash `_.uniq` import for one call. `[...new Set(xs)]`, 0 deps.`

✅ `parser.py:L88: yagni: BaseParser ABC with one subclass. Inline it until a second parser exists.`

✅ `L52-71: delete: retry wrapper around an idempotent local call. Nothing replaces it.`

✅ `L30-44: shrink: manual for-loop builds an array of names. `users.map(u => u.name)`, 1 line.`

## Scoring

End with: `net: -<N> lines possible.`

If nothing to cut: `Lean already. Ship.` and stop.

## Boundaries

Scope: over-engineering and complexity only. Correctness bugs, security
holes, and performance issues are **out of scope** — route them to the
`code-reviewer` agent. A single smoke test or assert is
the minimum — never flag the last test for deletion. Lists fixes, never
applies them.

---

*Adapted from [DietrichGebert/ponytail](https://github.com/DietrichGebert/ponytail) (MIT).*
