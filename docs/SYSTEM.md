# System description — claude-platform-setup

Status: 2026-10-29, after step 3.3 (2.8 dogfood issues pending the owner's labels-sync) of `docs/PLAN-2026-10-mature-setup.md`.
Components marked *planned* do not exist yet; the plan step that creates them is named.

## Purpose

A harness-neutral kit for AI-assisted platform engineering in regulated (GxP)
environments: a working agreement (`AGENTS.md`), skills, agents, deterministic
hooks and a task-tracker CLI, installed as files into a task repository so that
Claude Code and VS Code + GitHub Copilot enforce the same rules. The kit is
built to leave validation evidence behind: plan first, one topic per commit,
external verification with shown output, decisions recorded.

## Components and data flows

| Component | Today | Read by | Data |
|---|---|---|---|
| `AGENTS.md` (+ `CLAUDE.md` = `@AGENTS.md`) | exists | Claude Code; Copilot (VS Code, CLI, cloud); Codex; Gemini CLI | rules only |
| `agents/*.md` | exists (12, each pins `model:` opus/fable) | Claude Code via `~/.claude/agents` (`install.sh`); VS Code reads `.claude/agents` in task repos | prompts |
| `skills/*/SKILL.md` | exists | Claude Code via `~/.claude/skills`; Copilot via `.claude/skills` in task repos | procedures |
| `kit.manifest` + `install.sh --into <repo>` | exists (1.2) | — | copies the listed files into a task repo; writes `.claude/kit-version` and a hash manifest so locally edited files are kept |
| `tools/guard/guard.py` + `.claude/settings.json` + `.github/hooks/guard.json` | exists (1.2 engine + delete-guard; 1.4 secret-write/read/shell, git-guard, deploy-ask, egress-guard; 1.5 scratch-md; 2.1 guard-the-guard; 2.2 protected-branch; 2.3 fan-out + spawn log; 2.6 tracker-guard) | Claude Code hooks; Copilot hooks | hook JSON on stdin → `ask`/`deny` JSON (never `allow`); fixtures from both harnesses; no network |
| `tools/tracker/tracker.py` + label families + issue forms | exists (2.4, 2.5, 2.7: pr-prep and task-intake call it; session-start digest) | agents via the verbs, humans via `owner` verbs at a terminal; GitHub via `gh` | issues, labels, marker comments on GitHub |
| `tools/tracker/label_lint.py` + `.github/workflows/label-lint.yml` | exists (2.4) | GitHub Actions on issue events and nightly | comments and one tracking issue; never edits labels |
| `.githooks/commit-msg` + `tools/commit_msg.py` | exists (3.1) | git via `core.hooksPath`; CI job `commit-msg` on the PR range | commit messages |
| `tools/egress/egress_screen.py` | exists (3.2) | `fresh-review`, `gemini-review`, anything that sends material out | the material, held or sent, never dropped |
| `bin/fresh-review` + `tools/review/prompt.md` (= `.github/instructions/review.instructions.md`) | exists (3.3) | `claude -p` at home (Opus, no tools, JSON schema); Copilot code review at work | branch diff; receipt `.git/fresh-review/<sha>.json` |
| memory store, session ledger | planned (3.4–3.6) | Claude Code only | memory files (private repo); token usage (local) |
| `~/.claude/telemetry/spawns.jsonl` | exists (2.3) | fan-out rule; humans (`tail`) | one line per subagent spawn: ts, harness, agent, model; local only |

Flow: a human approves a plan → steps become GitHub issues (`tracker new`, a human
promotes with `owner ready`) → an agent claims one, works on a branch, opens a PR with `Refs #N` → CI and an independent
review → a human merges and closes with the protocol. Hooks sit in front of
every tool call in both harnesses.

## Environments

- Home: macOS, Claude Code (subscription), GitHub account `kacper38`; this repo dogfoods the kit.
- Work: VS Code + GitHub Copilot (hooks, skills and MCP policies enabled, per Kacper 2026-10-29);
  one pilot repo in plan step 3.9 with `KZ_BOUNDARY=client`. See `docs/USING-AT-WORK.md`.
- Deferred (plan Appendix A): self-hosted Forgejo, Proxmox host `pierun`, a CI runner VM.

## Interfaces

- GitHub via `gh` (issues, labels, PRs, checks); GitHub Actions for CI and `label-lint`; a ruleset on `main` (PR + green `ci`, no force push, no deletion).
- Claude Code hooks (`.claude/settings.json`) and Copilot hooks (`.github/hooks/*.json`,
  `.claude/settings.json`): JSON on stdin, `permissionDecision` on stdout, exit 2 = deny.
- `claude -p` for the home fresh-context review (through the egress screen); Copilot code review at work.

## Data classification

- This repo: public, MIT. No client data, no credentials, no transcripts, no hook captures before redaction.
- Telemetry (`~/.claude/telemetry/`) and raw hook captures: local to the machine; only redacted fixtures are committed.
- Memory: private GitHub repo, own notes only; client facts never enter memory.
- Work pilot: only the kit's public files cross over; findings stay in the work repo's own `DECISIONS.md`.
