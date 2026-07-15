---
name: data-pipeline
description: Build a data pipeline for AI systems — training data, RAG ingestion refresh, analytics, operational feeds from client systems. Use when the task moves data between systems, one-off or scheduled; triggers "data pipeline", "ETL", "feed", "sync from <system>", "ingestion refresh". Sibling of rag-stack, same one-verified-commit-per-stage rhythm.
---

# Data pipeline

Move regulated data with lineage by construction. One stage = one verified
commit. No orchestrator until the flip trigger fires — a cron'd job that
records its runs beats an idle Airflow.

## Stages

1. **Source contract** — pin the inbound schema (pydantic model per feed);
   validate at the boundary; reject-and-quarantine bad records (quarantine
   table or prefix, keeping reason + raw payload). A feed without a contract
   is an incident waiting for a quiet weekend.
   Verify: sample batch parses; a malformed record lands in quarantine, not the target.
2. **Idempotent extract/load** — hash or watermark based, re-run is a no-op;
   upserts, no blind appends; batch unless the task genuinely needs streaming.
   Verify: run twice on the same input; second run writes zero rows.
3. **Lineage record** — one `pipeline_runs` row per run: run id, source uri +
   version, code version (git SHA), rows in/out/quarantined, started/finished,
   status. This is ALCOA+ Original/Traceable applied to the transformation.
   Verify: run the job, select the row.
4. **Quality gates** — checks that fail the run loudly, never silently:
   row-count delta vs previous run, null/uniqueness thresholds on key columns,
   freshness (source older than agreed window = failure).
   Verify: feed it a doctored bad batch; the run fails with the reason in the run record.
5. **Schedule** — scheduled GitHub Actions / ECS scheduled task / Container
   Apps job running the same SHA-tagged image as the service; job failure is
   an alert, job success a metric. Flip trigger to Dagster/Airflow goes in
   DECISIONS.md ("revisit if: >5 dependent jobs or backfills become weekly work").
   Verify: one manual end-to-end trigger.

## Typical client sources (orientation — don't invent interfaces)

| System | Usual access |
|---|---|
| SAP | OData services / BAPI extracts — batch, not streaming; direct DB access is rare |
| LIMS / MES | vendor REST APIs or read-replica DB views |
| Historians (OSIsoft PI, OPC-UA) | PI Web API / OPC-UA gateway, time-series batches |
| Document management | vendor API + checksum per document (ALCOA+ Original) |
| Flat-file drops | SFTP + checksum manifest; the manifest is the contract |

## Non-negotiables

- Every new connection is a data boundary — client data stays inside the
  agreed one (CLAUDE.md rule 6); record the connection in DECISIONS.md.
- Pin everything: source schema version, image tag, transform code SHA.
- No hard deletes of regulated data — soft delete + audit table
  (postgres-engineer owns the pattern).
