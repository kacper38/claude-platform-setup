---
name: post-mortem
description: Blameless post-incident write-up — timeline, impact, root cause, corrective actions with owners. Use after resolving an incident or outage; triggers "post-mortem", "incident report", "co poszło nie tak".
---

# Post-mortem

Blameless, evidence-based, finished within 48h of resolution. The goal is the
action list, not the narrative.

## During the incident (before any write-up)

- Severity call first, then mitigate — root-causing waits until users stop
  bleeding; note which rollback/mitigation you chose.
- One comms line to stakeholders at the severity call and at resolution.
- Save evidence as it happens into `postmortems/YYYY-MM-DD-<slug>/`: log
  excerpts, alert screenshots, deploy SHAs, timestamps — the timeline below
  is assembled from artifacts, not memory.

## Structure (produce as `postmortems/YYYY-MM-DD-<slug>.md`)

1. **Summary** — one paragraph: what broke, for how long, who was affected.
2. **Impact** — measured against SLO/SLI where defined: duration, error rate,
   affected clients/requests, data integrity impact (yes/no — in GxP this line
   is mandatory; if yes, note whether a deviation report is needed).
3. **Timeline** — UTC timestamps from logs/alerts/deploys, detection → mitigation
   → resolution. Pull from real sources (pipeline logs, monitoring), don't
   reconstruct from memory.
4. **Root cause** — the condition that made the failure possible, not the
   trigger. Ask "why" until the answer is a process or design property.
   No names — systems and processes fail, not people.
5. **What went well / what didn't** — detection speed, runbook coverage,
   rollback path.
6. **Corrective actions** — each with owner, due date, and type:
   prevent (fix the cause), detect (alert earlier), mitigate (fail smaller).
   Include the monitoring/alert change that would have caught it sooner.
7. **Validation note** — if the fix touches a validated system: what re-testing
   or evidence update the change requires (link the validation-evidence pack).

## Rules

- Facts with evidence links; hypotheses labeled as such.
- One follow-up review date to check action completion — actions without a
  review date don't happen.
