---
name: gxp-check
description: Fast compliance + security sweep of the working tree, mapped to GxP vocabulary. Use before each significant commit, before a demo or release, or on "gxp check" / "compliance sweep". Complements the gxp-compliance-reviewer agent (this is the quick greppable pass; the agent does the deep review).
---

# GxP check

Mechanical sweep first, judgment second. Report as a table, fix blockers
immediately with user approval.

## Sweep (run all, show evidence)

1. **Secrets in code/state:**
   `grep -rniE '(api[_-]?key|secret|password|token)\s*[:=]' --exclude-dir={.git,node_modules,.venv,.terraform} .`
   plus check `*.tfstate`, `.env` committed? (`git ls-files | grep -E '\.env|tfstate'`)
2. **Container hygiene:** Dockerfile has `USER` (non-root)? `HEALTHCHECK`? base
   image pinned? no `latest` anywhere (`grep -rn 'latest' Dockerfile* *.yml .github/ terraform/ 2>/dev/null`)
3. **CI hygiene:** `permissions:` block present and minimal? OIDC not static
   keys (`grep -rn 'AWS_SECRET\|AZURE_CLIENT_SECRET' .github/`)? image tagged by SHA?
4. **IaC hygiene:** `terraform fmt -check && terraform validate`; grep for
   wildcard IAM (`grep -rn '"\*"' terraform/ | grep -i 'action\|resource'`)
5. **Debug leftovers:** `grep -rn 'print(\|console.log\|TODO\|FIXME' app/ src/ 2>/dev/null | head`

## Map findings to compliance vocabulary

For each finding, add the GxP hook in one clause:

| Finding | Hook |
|---|---|
| secret in repo/state | breaks audit-safe change control; vault + data source |
| shared/static CI keys | breaks Attributable — OIDC gives per-run identity |
| `latest` tag | breaks Traceable/reproducible — SHA tags are validation evidence |
| no tests before deploy | no validation evidence for the change |
| mutable/no logs | breaks Contemporaneous/Enduring — server-side, retained logs |
| untracked manual env change | breaks Original — IaC is the documented environment |

## Output

Pass/fail table per category with the evidence lines, then: "BLOCKERS: n — fix
before commit" or "clean — commit away", plus one audit-ready summary sentence, e.g.:
"Every change here is attributable and reproducible — git + OIDC + SHA-tagged
artifacts are the audit trail, tests and terraform plan are the validation evidence."
