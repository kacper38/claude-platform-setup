# Using this setup at work (VS Code + GitHub Copilot)

For a work machine with VS Code and GitHub Copilot, where Claude Code is not
installed. Status 2026-10-29: plan step 1.1 is done, so §1 is usable today;
§2 lists what each later step adds. Copilot's hooks, skills and MCP policies
are enabled in the org (confirmed by Kacper).

## 0. Boundaries first

- Only the kit's public MIT files cross over. Nothing from home: no memory,
  telemetry, tokens, transcripts or hook captures.
- Client data never enters the kit, a hook fixture, a memory file or a prompt
  beyond the endpoint the org approved. `AGENTS.md` rule 6 applies on day one.
- Findings about the work environment (model names, policies, tool ids) go to
  the work repo's own `DECISIONS.md`, never to this repo.
- Pick one low-risk pilot repo you are allowed to configure, on GitHub
  Enterprise if possible (plan question Q-B). Work on a branch and open a PR.

## 1. Usable today

Copy into the pilot repo:

```bash
cp AGENTS.md <repo>/AGENTS.md
mkdir -p <repo>/.claude && cp -R skills <repo>/.claude/skills && cp -R agents <repo>/.claude/agents
```

Then adapt, in the work repo:

1. **`AGENTS.md`**: keep the eight non-negotiables and the four coding
   principles; replace "Default stack choices" with the org's stack; in the
   routing table, substitute the model names the Copilot picker offers.
   Record every change as a DECISIONS line.
2. **Instructions attach?** Open a new Copilot chat and check the references
   list shows `AGENTS.md`. If not, the org has `chat.useAgentsMdFile` off:
   add `.github/copilot-instructions.md` containing one line, "Read AGENTS.md
   first and follow it", and record it.
3. **Skills**: `.claude/skills/` is read by Copilot as is. Type `/skills` to
   see them; the ones that matter first are task-intake, platform-flow,
   gxp-check, validation-evidence, verify, pr-prep and post-mortem.
4. **Agents**: `.claude/agents/` appears in the agent picker. Ask the
   `infra-reviewer` to change a file: it must refuse. If it does not, Claude
   tool names are ignored there; add Copilot identifiers in the same
   frontmatter (`tools: ['read', 'search']`) and record it.
5. **Scaffold** each task repo with `/task-intake`: README, DECISIONS.md,
   docs/SYSTEM.md, a plan approved before code.
6. **Walk test** in a fresh chat: "Quote non-negotiable 3 verbatim" must come
   back from `AGENTS.md`; "where does task state live" must name the tracker
   (`tools/tracker`, GitHub Issues with the `type/*` and `status/*` families).

## 2. What later plan steps add, and what to do with each at work

| Plan step | Kit piece | At work |
|---|---|---|
| 1.2–1.5 | `tools/guard` with `.claude/settings.json` and `.github/hooks/guard.json` | copy both wrappers and `tools/guard`; test: `cat .env` → ask, `git push --force` → deny, `terraform apply` → ask; the cloud agent turns `ask` into `deny`; hooks must finish under 2 s because Copilot timeouts fail open |
| 1.6 | model pins in agent frontmatter | substitute picker names; the cloud agent ignores `model:` |
| 2.2 | protected-branch hook | set the protected list in `.claude/guard.json` to the org's branches |
| 2.4–2.7 | `tracker` on GitHub Issues, label families, `label-lint.yml` | works as is on GitHub Enterprise after `gh auth login --hostname <ghe>`; on Jira or Azure DevOps the CLI stays read-only until an adapter exists; put the ticket key in the commit trailer meanwhile |
| 3.1 | `commit-msg` hook | `git config core.hooksPath .githooks` per clone; if the org forbids AI attribution, disable the trailer knob and record it |
| 3.2 | egress screen | in front of anything that leaves the machine; the client marker list comes from the work repo |
| 3.3 | review instructions | commit `.github/instructions/review.instructions.md`; Copilot code review on the PR follows it; the human approval stays the control |
| 3.9 | work pilot | the formal step: run the checks above, write the pilot's DECISIONS lines, demo to the team |

## 3. Org-level pieces (propose, do not do alone)

These need platform or security sign-off and are the ones an auditor counts
as controls rather than habits:

- Custom agents for every repo in the org: `agents/*.md` in the org's
  `.github-private` repository (test them under `.github/agents/` there first).
- Enterprise `copilot/managed-settings.json` in the designated
  `.github-private`: policy developers cannot override.
- A bot identity (GitHub App) for agent-authored PRs, so the author is never
  the approver.
- Rulesets on `main`: required checks, CODEOWNERS, one human approval; Copilot
  code review auto-requested.
- MCP allowlist by org policy (this kit needs no MCP server).

## 4. Saying it in GxP terms

- Hooks are technical controls: deterministic, tested with fixtures in CI,
  versioned by the commit in `.claude/kit-version`.
- The tracker protocol is "who may perform which transition" as code; the PR
  with green checks on the merge SHA is the evidence; `Refs #N` (or the Jira
  key) is the traceability link to the change record.
- AI review is supporting evidence. The human approval is the control.
- The evidence pack (`/validation-evidence`) is the requirement → implementation
  → test matrix with captured outputs, ready for a CSV package.

## 5. Differences to keep in mind

| Claude Code | Copilot |
|---|---|
| hook timeout = the hook's decision is lost, call blocked by default settings | timeout fails open, every event |
| `ask` prompts the user | VS Code prompts; CLI prompts; cloud agent denies |
| tool names `Bash`, `Read`, `Write`, `Edit`, `Agent` | `bash`, `view`, `create`, `edit`, `task` (guard normalizes) |
| `permissions.deny` in settings | ignored; the PreToolUse hook carries the rule |
| SessionEnd ledger, statusline | none in VS Code; use the org's Copilot usage dashboard |
| `model:` aliases (`opus`) | picker display names; ignored by the cloud agent |

## 6. First-day checklist

1. Pilot repo chosen; branch created.
2. `AGENTS.md` adapted; instructions attach in a fresh chat (or the fallback file exists).
3. `.claude/skills` and `.claude/agents` copied; `/skills` and the picker show them.
4. A read-only agent refuses to edit.
5. Walk test passes.
6. Work repo `DECISIONS.md` records: harness facts, model mapping, what was skipped and why.
7. PR opened; a teammate reviews the scaffold.
