---
name: rag-stack
description: Stand up or extend RAG infrastructure — pgvector locally via compose, managed Postgres in Terraform, ingestion job, traceability logging, cost metrics, private LLM endpoints. Use when the task includes retrieval/LLM components; triggers "rag stack", "add retrieval", "vector store setup".
---

# RAG stack

Infrastructure for a RAG service, built in the platform-flow rhythm (one
stage = one verified commit). Architecture decisions go through the
`rag-infra-advisor` agent first if they're not already in DECISIONS.md.

## Stages

1. **Local vector store** — `docker-compose.yml` service: `pgvector/pgvector:pg16`
   (pinned), volume, healthcheck; init SQL enabling `CREATE EXTENSION vector`.
   Verify: `docker compose up -d db && psql ... -c 'select 1'`.
2. **Schema with traceability built in** — documents (id, source uri, version,
   hash), chunks (doc fk, position, embedding vector, embed-model tag),
   answers log (query, chunk ids used, prompt version, model id, latency,
   token counts, caller, timestamp). Verify: migration applies clean.
3. **Ingestion job** — idempotent (re-run skips unchanged docs by hash),
   batch embeddings, records doc version + embed model per chunk.
   Verify: run on sample docs twice; second run is a no-op.
4. **Query path** — top-k retrieval + prompt assembly; every response returns
   source citations and writes the answers-log row. Verify: curl the endpoint,
   check the log row exists and cites real chunks.
5. **IaC** — managed Postgres (RDS / Flexible Server) with pgvector, private
   networking to the LLM endpoint (Azure OpenAI VNet / Bedrock VPC endpoint),
   secrets from vault. Verify: `terraform validate` + review plan.
6. **Cost + eval hooks** — token count and cost-per-query metric exported;
   golden-set retrieval eval runnable in CI (`recall@k`), report saved as
   artifact. Verify: eval runs green on the sample set.

## Non-negotiables

- Pin everything: image tags, embedding model, LLM model version, prompt
  template version — an unpinned alias is an uncontrolled change.
- Client data stays inside the agreed boundary; no public API calls with
  client content unless explicitly approved and recorded in DECISIONS.md.
- Every answer reconstructable from the answers log (ALCOA+ across the
  data → retrieval → answer chain).
