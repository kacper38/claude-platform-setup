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
./claude-platform-setup/install.sh     # copies agents + skills to ~/.claude,
                                       # backs up anything it would overwrite,
                                       # writes an uninstall manifest
cd <your-task-repo> && claude
/task-intake                           # paste the task — the rest follows
```

Remove it cleanly with `./install.sh --uninstall` (deletes exactly what the
manifest lists; backups stay in `~/.claude/backups/`).

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
| `node-engineer` | Production TypeScript: Next.js frontends, zod at boundaries; npm ci + tsc + vitest |
| `shell-engineer` | Bash that survives production: `set -euo pipefail`, quoting, shellcheck, traps — and knows when to switch to Python |
| `k8s-engineer` | Manifests (probes, limits, securityContext), Kustomize/Helm, pod-debugging runbook, EKS/AKS, GitOps |
| `git-surgeon` | Conflicts, reflog recovery, bisect, history surgery behind a backup branch; signed commits as audit trail |
| `observability-engineer` | Prometheus/Grafana as code, symptom-based alerting, SLOs, correlation ids, LLM cost metrics |
| `postgres-engineer` | Non-blocking migrations, EXPLAIN/indexing, restore-tested backups, RLS, pgvector tuning |
| `code-reviewer` | General code review: correctness, security, maintainability |

## Skills — task lifecycle

| Skill | When |
|---|---|
| `/task-intake` | New task/ticket → assumptions, questions, scaffolding (README, DECISIONS.md, AGENTS.md), approved plan |
| `/platform-flow` | The chain: local dev → Docker → CI → Terraform → CD → observability → security |
| `/rag-stack` | RAG component: pgvector, traceability-first schema, idempotent ingestion, private endpoints, eval + cost hooks |
| `/data-pipeline` | Data feed/ETL: source contract + quarantine, idempotent load, lineage row per run, quality gates, scheduled job |
| `/gxp-check` | Before significant commits — secrets/tags/IAM/vuln-scan/pipeline-lineage sweep mapped to GxP vocabulary |
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

## Tracker — GitHub Issues as the system of record

`tools/tracker/tracker.py` is the only writer of issues and labels an agent uses
(the `tracker-guard` hook denies `gh issue …`, `gh label …` and raw API writes).
State lives in two label families, `type/*` and `status/*`, with a transition
table that says who may move what:

```
tracker new --title "…" --ac "…" --scope "…" --scope-limit "…" --source "…"   # agent: lands in status/backlog
tracker owner ready N          # human at a terminal: definition of ready, freezes the body
tracker claim N                # agent: ready -> in-progress, one per actor, records the branch
tracker block N --question "…" # agent: in-progress -> blocked, question must name a path or field
tracker review N --pr <url>    # agent: in-progress -> review; PR head = claimed branch, body has `Refs #N`
tracker owner done N           # human: merged PR, green checks on the merge SHA, every box ticked or waived
tracker list | show N | note N "…" | owner labels-sync
```

Owner verbs refuse without a TTY, so an agent cannot promote or close. The
`label-lint` workflow reports label mistakes (comment + one tracking issue) and
never edits them. Issue forms under `.github/ISSUE_TEMPLATE/` carry the
definition-of-ready fields.

## Working agreement

[`AGENTS.md`](AGENTS.md) — eight non-negotiables (plan first, small steps,
evidence over claims, DECISIONS.md, regulated context, security reflexes,
named gaps, back out of bad paths), the four Karpathy coding principles
(think before coding, simplicity first, surgical changes, goal-driven
execution — adapted from
[andrej-karpathy-skills](https://github.com/multica-ai/andrej-karpathy-skills)),
the model-routing table and notes on which harness reads what. `CLAUDE.md`
is the one line `@AGENTS.md`, so Claude Code loads the same file that GitHub
Copilot, Codex and Gemini CLI read directly. `/task-intake` copies both into
the task repo, so the principles are always active where you work.

Decisions live in [`DECISIONS.md`](DECISIONS.md); the one-page system
description in [`docs/SYSTEM.md`](docs/SYSTEM.md); the current plan in
[`docs/PLAN-2026-10-mature-setup.md`](docs/PLAN-2026-10-mature-setup.md).

A one-page visual overview lives in
[`setup-overview.html`](setup-overview.html) (Polish). A non-normative study
guide for the target role's tech stack (with a personal CV gap map) lives in
[`tech-primer.html`](tech-primer.html) — the `.md` files are the authority.

## Install into a repo (the kit)

The setup is becoming a repo-level kit that Claude Code **and** VS Code +
GitHub Copilot read from the same files: `AGENTS.md`, `.claude/settings.json`
(hooks), `.claude/skills/`, `.claude/agents/`, `.github/hooks/`,
`tools/guard`, `tools/tracker`. `install.sh --into <repo>` arrives with step
1.2 of the plan. Until then, copy by hand:

```bash
cp AGENTS.md <repo>/AGENTS.md && printf '@AGENTS.md\n' > <repo>/CLAUDE.md
mkdir -p <repo>/.claude && cp -R skills <repo>/.claude/skills && cp -R agents <repo>/.claude/agents
```

Using it on a work machine with VS Code + GitHub Copilot:
[`docs/USING-AT-WORK.md`](docs/USING-AT-WORK.md).

## License

MIT
