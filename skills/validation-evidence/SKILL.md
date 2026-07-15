---
name: validation-evidence
description: Assemble an audit-grade evidence pack for a change, feature, or release — requirement→implementation→test traceability plus captured check outputs. Use before a release, client handoff, or QA review; triggers "validation evidence", "evidence pack", "audit pack", "RTM".
---

# Validation evidence

Turn what the pipeline already produces into a reviewable evidence pack.
No paperwork theater: everything here is generated from real artifacts.

## Steps

1. **Scope.** Confirm the unit: a PR, a release tag, or a date range.
   List the requirements/stories it claims to satisfy (from the ticket,
   README scope section, or ask).
2. **Traceability matrix (RTM-lite).** One row per requirement:

   | Req | Implementation (files/commits) | Test / check | Evidence |
   |---|---|---|---|
   | REQ-01 short name | `path/file.py` @ `abc123` | `tests/test_x.py::test_y` | run output ref |

   Requirements with no test row are findings, not omissions to hide.
3. **Capture check outputs.** Run and save verbatim into `evidence/<tag>/`:
   test run (`pytest -q` / `npm test`), lint (`ruff` / `eslint` +
   `tsc --noEmit`), `docker build` digest (+ `next build` where applicable),
   `terraform plan` summary, image SHA + registry digest, vulnerability scan
   report (trivy / pip-audit / npm audit), SBOM where configured
   (`syft <image> -o spdx-json`), eval report if AI-touching.
4. **Change control trail.** `git log --oneline` for the scope, PR links +
   approvers, deployment approval records (environment protection), and
   DECISIONS.md entries relevant to this unit.
5. **System description.** Confirm `docs/SYSTEM.md` still matches reality
   (fields per task-intake); update it within this release's scope. Auditors
   read it before any evidence pack.
6. **Gaps.** Explicit list: untested requirements, manual steps performed,
   known deviations — each with owner and follow-up.

## Output

`evidence/<tag>/SUMMARY.md` containing: scope, RTM table, links to captured
outputs, change trail, pointer to `docs/SYSTEM.md`, gaps. One screen; a QA
reviewer should get to "approve or ask" in five minutes. Commit the pack — evidence that can drift isn't
evidence (Enduring).
