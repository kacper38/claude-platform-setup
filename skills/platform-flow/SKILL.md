---
name: platform-flow
description: The code-to-running chain for a service — local dev → container → CI → IaC → CD → observability → security. Use after task-intake approval to execute the plan, or when asked "what's next in the flow". Each stage ends with verification and one commit.
---

# Platform flow

Execute the standard chain, one stage = one (or few) commits, each verified
before moving on. Skip or reorder stages only when the plan says so — and say why.

## Stages

1. **Local dev** — run the app locally; `docker-compose.yml` for dependencies
   (db, vector store). Verify: app responds locally.
2. **Containerize** — multi-stage Dockerfile: deps layer → runtime layer,
   non-root user (`useradd -m -u 10001 appuser`), slim base, HEALTHCHECK,
   exec-form CMD, `.dockerignore`. Verify: `docker build` + run + hit `/health`.
3. **CI** — GitHub Actions: `ruff check` → `pytest -q` → `docker build` →
   `trivy image --exit-code 1 --severity HIGH,CRITICAL` → push to registry.
   Dependency audit next to lint (`pip-audit` / `npm audit --audit-level=high`
   where a lockfile exists). `permissions: {id-token: write, contents: read}`;
   OIDC role, no stored cloud keys; tag = `${{ github.sha }}`. Verify: workflow
   syntax (act or push), steps ordered fail-fast, scan gating before push.
4. **IaC** — Terraform module skeleton: `modules/network`, `modules/service`
   (ECS Fargate + ALB on AWS, or Container Apps on Azure), `variables.tf`,
   `outputs.tf` (service URL), remote backend + locking (S3+DynamoDB /
   azurerm) — declared even if mocked. Secrets via data source into Secrets
   Manager / Key Vault, never in state. Verify: `terraform fmt -check`,
   `terraform validate`, review `plan` output with the user.
5. **CD** — deploy job in the pipeline gated on CI, environments (dev → prod)
   with controlled promotion. Verify: pipeline graph makes sense end-to-end.
6. **Observability** — `/health` endpoint, structured JSON logs, one metric
   and one alert sketched (CloudWatch / Azure Monitor). Verify: endpoint
   answers, log line shows correlation id.
7. **Security & compliance sweep** — run the `gxp-check` skill; fix blockers.

## LLM/RAG addendum (when the task includes it)

- vector store: pgvector via compose locally; managed (RDS/Flexible Server) in IaC
- answer traceability: log which chunks/sources fed each response — GxP requirement, mention it
- cost controls: token limits, response/embedding caching, model choice per task, cost-per-query metric
- data boundary: client data never to public API endpoints — private endpoints (Azure OpenAI in VNet / Bedrock) in the IaC story

## Timeboxing

At each stage boundary state: stages left and what falls below the cut line if
the budget is tight. "End-to-end skeleton with named gaps" beats "perfect stage
3 of 7". Record every deliberate gap in DECISIONS.md with its upgrade trigger.
