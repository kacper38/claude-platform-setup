# claude-platform-setup

An opinionated [Claude Code](https://claude.com/claude-code) setup for
**platform engineering in regulated (GxP) environments** — taking a service
from ticket to running, auditable infrastructure, with AI/RAG workloads as a
first-class concern.

The premise: the engineer decides, plans, and verifies; the agent executes.
Every change must be defensible as validation evidence — plan first, one topic
per commit, external verification with shown output, decisions recorded.

## Install

```bash
git clone https://github.com/kacper38/claude-platform-setup.git
./claude-platform-setup/install.sh     # copies agents + skills to ~/.claude
cd <your-task-repo> && claude
/task-intake                           # paste the task — the rest follows
```

## Agents

Process & compliance core:

| Agent | Role |
|---|---|
| `platform-planner` | Plan before code: assumptions, questions, steps with a verification command each, trade-offs, cut line |
| `infra-reviewer` | Dockerfile / GitHub Actions / Terraform / compose review — correctness and best practices |
| `gxp-compliance-reviewer` | Same artifacts through a GAMP 5 auditor's lens: audit trail, ALCOA+, validation evidence |
| `rag-infra-advisor` | AI-infra decisions: vector store, private LLM endpoints, model+prompt+index versioning, eval in CI, cost, data residency |

Execution bench:

| Agent | Role |
|---|---|
| `python-engineer` | Production Python: FastAPI, CLIs, automation; uv + ruff + mypy + pytest |
| `shell-engineer` | Bash that survives production: `set -euo pipefail`, quoting, shellcheck, traps — and knows when to switch to Python |
| `k8s-engineer` | Manifests (probes, limits, securityContext), Kustomize/Helm, pod-debugging runbook, EKS/AKS, GitOps |
| `git-surgeon` | Conflicts, reflog recovery, bisect, history surgery behind a backup branch; signed commits as audit trail |
| `observability-engineer` | Prometheus/Grafana as code, symptom-based alerting, SLOs, correlation ids, LLM cost metrics |
| `postgres-engineer` | Non-blocking migrations, EXPLAIN/indexing, restore-tested backups, RLS, pgvector tuning |
| `code-reviewer` | General code review: correctness, security, maintainability |

## Skills — task lifecycle

| Skill | When |
|---|---|
| `/task-intake` | New task/ticket → assumptions, questions, scaffolding (README, DECISIONS.md, CLAUDE.md), approved plan |
| `/platform-flow` | The chain: local dev → Docker → CI → Terraform → CD → observability → security |
| `/rag-stack` | RAG component: pgvector, traceability-first schema, idempotent ingestion, private endpoints, eval + cost hooks |
| `/gxp-check` | Before significant commits — secrets/tags/IAM sweep mapped to GxP vocabulary |
| `/validation-evidence` | Before release/handoff — evidence pack: requirement→implementation→test matrix, captured outputs, change trail |
| `/post-mortem` | After an incident — blameless write-up with owners and a validation note |

Plus general support: `verify`, `code-review`, `pr-prep`, `systematic-debugging`,
`verification-before-completion`.

Anti-over-engineering (the lazy family):

| Skill | When |
|---|---|
| `/ponytail` | Lazy mode for the whole session — the YAGNI → stdlib → native → installed-dep → one-line ladder (`lite\|full\|ultra`) |
| `/ponytail-review` | Review the current diff for things to DELETE: reinvented stdlib, unneeded deps, speculative abstractions |
| `/ponytail-audit` | Same lens over the whole repo — ranked by removable lines/deps |
| `/ponytail-debt` | Harvest `ponytail:` markers into a debt ledger with upgrade triggers |

## Working agreement

[`CLAUDE.md`](CLAUDE.md) — eight non-negotiables (plan first, small steps,
evidence over claims, DECISIONS.md, regulated context, security reflexes,
named gaps, back out of bad paths) plus the four Karpathy coding principles
(think before coding, simplicity first, surgical changes, goal-driven
execution — adapted from
[andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills)).
`/task-intake` copies it into the task repo, so the principles are always
active where you work.

A one-page visual overview lives in
[`setup-overview.html`](setup-overview.html) (Polish).

## License

MIT
