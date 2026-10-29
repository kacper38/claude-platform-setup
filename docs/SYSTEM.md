# System description — claude-platform-setup

Status: 2026-10-29, after step 1.5 of `docs/PLAN-2026-10-mature-setup.md`.
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
| `agents/*.md` | exists (12) | Claude Code via `~/.claude/agents` (`install.sh`); VS Code reads `.claude/agents` in task repos | prompts |
| `skills/*/SKILL.md` | exists | Claude Code via `~/.claude/skills`; Copilot via `.claude/skills` in task repos | procedures |
| `kit.manifest` + `install.sh --into <repo>` | exists (1.2) | — | copies the listed files into a task repo; writes `.claude/kit-version` and a hash manifest so locally edited files are kept |
| `tools/guard/guard.py` + `.claude/settings.json` + `.github/hooks/guard.json` | exists (1.2 engine + delete-guard; 1.4 secret-write/read/shell, git-guard, deploy-ask, egress-guard; 1.5 scratch-md); more rules planned (2.1–2.3) | Claude Code hooks; Copilot hooks | hook JSON on stdin → `ask`/`deny` JSON (never `allow`); fixtures from both harnesses; no network |
| `tools/tracker` + label families + `label-lint.yml` | planned (2.4–2.7) | humans and agents via the CLI; GitHub via `gh` | issues, labels, comments on GitHub |
| `.githooks/commit-msg`, fresh review, egress screen | planned (3.1–3.3) | git; `claude -p` at home; Copilot code review at work | diffs, screened before they leave the machine |
| memory store, session ledger | planned (3.4–3.6) | Claude Code only | memory files (private repo); token usage (local) |

Flow: a human approves a plan → steps become GitHub issues (planned) → an agent
claims one, works on a branch, opens a PR with `Refs #N` → CI and an independent
review → a human merges and closes with the protocol. Hooks sit in front of
every tool call in both harnesses.

## Environments

- Home: macOS, Claude Code (subscription), GitHub account `kacper38`; this repo dogfoods the kit.
- Work: VS Code + GitHub Copilot (hooks, skills and MCP policies enabled, per Kacper 2026-10-29);
  one pilot repo in plan step 3.9 with `KZ_BOUNDARY=client`. See `docs/USING-AT-WORK.md`.
- Deferred (plan Appendix A): self-hosted Forgejo, Proxmox host `pierun`, a CI runner VM.

## Interfaces

- GitHub via `gh` (issues, labels, PRs, checks); GitHub Actions for CI and `label-lint`.
- Claude Code hooks (`.claude/settings.json`) and Copilot hooks (`.github/hooks/*.json`,
  `.claude/settings.json`): JSON on stdin, `permissionDecision` on stdout, exit 2 = deny.
- `claude -p` for the home fresh-context review (through the egress screen); Copilot code review at work.

## Data classification

- This repo: public, MIT. No client data, no credentials, no transcripts, no hook captures before redaction.
- Telemetry (`~/.claude/telemetry/`) and raw hook captures: local to the machine; only redacted fixtures are committed.
- Memory: private GitHub repo, own notes only; client facts never enter memory.
- Work pilot: only the kit's public files cross over; findings stay in the work repo's own `DECISIONS.md`.
