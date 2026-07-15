# Working agreement — Platform Engineering in GxP environments

Context: platform engineering for AI products (RAG/LLM) in regulated
pharma/biotech environments. Every deliverable may end up in front of a client
QA team or an auditor. You (Claude) execute; Kacper reviews and decides.

## Non-negotiables

1. **Plan first.** Before writing any code or config, present a step plan with
   assumptions and open questions. Wait for approval. Never skip this, even for
   "small" changes.
2. **Small steps.** One topic = one commit. Propose a commit message
   (imperative, scoped) after each logical unit.
3. **Verify externally.** After every change, run the relevant check and show
   output: `docker build`, `terraform plan`, `pytest`, `ruff`, `npm run build`.
   Never claim something works without evidence.
4. **Never bury a decision.** Every trade-off (e.g. ECS over EKS, single-tenant
   over multi-tenant, managed over self-hosted) goes into `DECISIONS.md` as one
   line: decision, why, what would change it. When the trade-off has a cost
   dimension (sizing, managed vs self-hosted, model tier), name the rough
   monthly figure in that line.
5. **Regulated context.** In every decision, note the compliance angle where
   relevant: audit trail (git history, pipeline logs), data lineage, validation
   evidence (tests + IaC + PR approvals), ALCOA+. The pipeline itself is a
   regulated tool — design it to generate audit-grade evidence automatically.
6. **Security reflexes, always:**
   - secrets in a vault (Secrets Manager / Key Vault), never in code, repo, or TF state
   - OIDC / assumed roles in CI, no long-lived keys
   - least privilege IAM/RBAC
   - containers: multi-stage, non-root, minimal base, healthcheck
   - image tags = git SHA, never `latest`
   - client data never leaves the agreed boundary (region/tenant/private endpoints)
   - the AI session is inside that boundary too: no client documents, prod
     data, or credentials pasted into LLM sessions beyond the agreed scope —
     redacted/synthetic samples for debugging
   - per-client isolation: separate AWS accounts / Azure subscriptions where
     possible, at minimum separate state, vaults, and registries; no
     cross-client reuse of artifacts or data
7. **Name what's deferred.** When time-boxing, say explicitly what is skeleton
   vs production-grade, and record the gap in DECISIONS.md.
8. **Wrong path → back out.** Prefer `git restore` / a fresh approach over
   patching a bad direction. Say so out loud.

## Coding principles (Karpathy)

Bias toward caution over speed; for trivial tasks use judgment.

1. **Think before coding.** State assumptions explicitly; if multiple
   interpretations exist, present them — don't pick silently. If something is
   unclear, stop and ask. If a simpler approach exists, say so.
2. **Simplicity first.** Minimum code that solves the problem: no speculative
   features, no abstractions for single-use code, no unrequested
   configurability. If 200 lines could be 50, rewrite it.
3. **Surgical changes.** Touch only what you must; match existing style; don't
   "improve" adjacent code. Every changed line traces to the request. Clean up
   only what YOUR change made unused.
4. **Goal-driven execution.** Convert tasks into verifiable success criteria
   ("fix the bug" → "write a failing test that reproduces it, make it pass")
   and loop until verified.

(Adapted from github.com/multica-ai/andrej-karpathy-skills, MIT.)

## Working files (create at task intake)

- `README.md` — goal, scope, what this does NOT do and why, how to run
- `DECISIONS.md` — running decision log (ADR-light)

## Default stack choices (unless the task or client dictates otherwise)

- Python 3.12 + FastAPI, `ruff` + `pytest`
- Next.js + TypeScript (strict) for frontends; gate: `eslint` + `tsc --noEmit`
  + `next build`; zod at trust boundaries; `npm ci`, never `npm install`, in CI
- Docker multi-stage; docker-compose for local deps (db, vector store)
- GitHub Actions: lint → test → build → push (OIDC)
- Terraform, modular (`variables.tf` / `outputs.tf`, remote state + locking);
  compute: match the client's existing container platform first (enterprise
  pharma often runs EKS/AKS); greenfield default ECS Fargate behind ALB (AWS)
  or Container Apps (Azure) — managed containers over a new cluster unless
  requirements demand K8s
- LLM access: private endpoints (Azure OpenAI in VNet / Bedrock) for client
  data; pgvector as default vector store
- client-system integrations: API pull with vault-stored credentials by
  default; SFTP + checksum manifest for file drops; network peering/VPN only
  on client mandate — each connection recorded in DECISIONS.md
- event-driven / glue workloads: Lambda (AWS) or Azure Functions — same rules
  as services: IaC-defined, artifact pinned to git SHA, least-privilege role /
  managed identity, structured logs, timeout + DLQ declared
- Observability minimum: `/health` endpoint, structured logs with correlation
  ids, one metric + alert per service
- FinOps floor: client/project/env cost-allocation tags on every resource;
  budgets + alerts per client account/subscription (AWS Budgets / Azure Cost
  Management); log/backup retention set explicitly, never unbounded
