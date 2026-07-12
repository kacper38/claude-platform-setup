---
name: task-intake
description: Start-of-task ritual for platform work. Use when a new task, ticket, or client request arrives, before any code. Triggers "task intake", "nowe zadanie", "mamy zadanie", "start the task". Produces assumptions, open questions, scaffolding files, and an approved plan.
---

# Task intake

Turn a raw task statement (ticket, client email, spec) into an approved plan
and a scaffolded workspace. Nothing gets built before this completes.

## Steps

1. **Ingest.** Read the task statement twice. Read any provided repo fully
   (structure, deps, existing configs, CI).
2. **Assumptions & questions.** Write two numbered lists: assumptions you're
   making, and questions worth confirming with the requester (client, PO,
   reviewer). Keep questions to the 3-5 that actually change the approach.
3. **Scaffold** (in the task repo, where not already present):
   - `README.md` — goal, scope, explicit "not doing X because Y" section
   - `DECISIONS.md` — decision log with format: `- <decision> — <why>; revisit if: <trigger>`
   - `CLAUDE.md` — copy this setup's working agreement, append the task's assumptions
4. **Plan.** Delegate to the `platform-planner` agent (or produce the same
   structure inline): assumptions, questions, step plan with per-step
   verification commands, trade-offs, cut line.
5. **Confirm.** Present the plan. STOP and wait for explicit approval or edits.
   Do not start step 1 of the plan until approved.
6. **First commit.** After approval: `git init` if needed, commit the scaffolding
   (`chore: scaffold task workspace with plan and assumptions`).

## Output

End with the plan, the list of created files, and the first step you'll take
once approved. Intake should cost minutes, not hours — it pays for itself the
first time a wrong assumption would have burned an afternoon.
