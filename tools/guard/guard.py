#!/usr/bin/env python3
"""guard — deterministic hook engine for Claude Code and GitHub Copilot.

Standard library only, Python >= 3.9. Reads one hook event as JSON on stdin,
normalizes it across harnesses, runs the registered rules and answers with a
permission decision. It never emits "allow": staying silent leaves the
harness's own permission flow untouched (an explicit "allow" would bypass it).

Exit codes: 0 = no objection or "ask" (JSON on stdout); 2 = deny (JSON on
stdout, reason on stderr); 1 = guard itself failed (nothing on stdout).

Usage:
  guard.py hook pre [--wrapper claude|github]   run every PreToolUse rule
  guard.py hook <rule> [--wrapper ...]          run one rule (tests, debugging)
  guard.py hook capture [--wrapper ...]         record redacted raw input, never blocks
  guard.py rules | help | version
"""

import datetime as _dt
import json
import os
import re
import shlex
import subprocess
import sys
from typing import Callable, Optional

VERSION = "0.2.0"

# ----------------------------------------------------------------------------
# Harness normalization
# ----------------------------------------------------------------------------

CLAUDE_TOOLS = {
    "Bash": "shell",
    "Read": "read",
    "Write": "write",
    "Edit": "edit",
    "MultiEdit": "edit",
    "NotebookEdit": "edit",
    "Agent": "spawn",
    "Task": "spawn",
    "Glob": "search",
    "Grep": "search",
    "WebFetch": "web",
    "WebSearch": "web",
}
COPILOT_TOOLS = {
    "bash": "shell",
    "powershell": "shell",
    "view": "read",
    "create": "write",
    "edit": "edit",
    "task": "spawn",
    "glob": "search",
    "grep": "search",
    "web_fetch": "web",
    "web_search": "web",
}
EVENT_NAMES = {
    "pretooluse": "PreToolUse",
    "posttooluse": "PostToolUse",
    "posttoolusefailure": "PostToolUseFailure",
    "sessionstart": "SessionStart",
    "sessionend": "SessionEnd",
    "userpromptsubmit": "UserPromptSubmit",
    "userpromptsubmitted": "UserPromptSubmit",
    "stop": "Stop",
    "agentstop": "Stop",
    "subagentstart": "SubagentStart",
    "subagentstop": "SubagentStop",
    "precompact": "PreCompact",
    "notification": "Notification",
    "permissionrequest": "PermissionRequest",
}


class Event:
    """One hook invocation, the same shape whichever harness sent it."""

    def __init__(self, raw: dict):
        self.raw = raw
        name = raw.get("hook_event_name") or raw.get("hookEventName") or ""
        self.event = EVENT_NAMES.get(str(name).lower(), str(name))
        self.tool = str(raw.get("tool_name") or raw.get("toolName") or "")
        args = raw.get("tool_input") if "tool_input" in raw else raw.get("toolArgs")
        self.args: dict = args if isinstance(args, dict) else {}
        if self.tool in CLAUDE_TOOLS:
            self.harness = "claude"
        elif self.tool in COPILOT_TOOLS:
            self.harness = "copilot"
        elif "toolName" in raw or "toolArgs" in raw or "timestamp" in raw:
            self.harness = "copilot"
        elif "transcript_path" in raw or "permission_mode" in raw:
            self.harness = "claude"
        else:
            self.harness = "unknown"
        self.kind = CLAUDE_TOOLS.get(self.tool) or COPILOT_TOOLS.get(self.tool) or "other"
        self.cwd = str(raw.get("cwd") or os.getcwd())
        self.session = str(raw.get("session_id") or raw.get("sessionId") or "")
        self.command = _first_str(self.args, "command", "cmd", "commandLine", "script")
        self.path = _first_str(self.args, "file_path", "path", "filePath", "file", "notebook_path")
        self.content = _first_str(self.args, "content", "file_text", "new_source", "text")

    def abspath(self) -> Optional[str]:
        if not self.path:
            return None
        p = os.path.expanduser(self.path)
        if not os.path.isabs(p):
            p = os.path.join(self.cwd, p)
        return os.path.normpath(p)


def _first_str(d: dict, *keys: str) -> Optional[str]:
    for k in keys:
        v = d.get(k)
        if isinstance(v, str) and v:
            return v
    return None


# ----------------------------------------------------------------------------
# Config and knobs
# ----------------------------------------------------------------------------

DEFAULTS = {
    "telemetry_dir": "~/.claude/telemetry",
    "protected_branches": ["main"],
    "boundary": "own",
    "scratch_md_mode": "ask",  # ask | deny | off
    "scratch_md_allow": [
        "docs/", ".claude/", ".github/", "skills/", "agents/", ".agents/", "evidence/",
        "README.md", "DECISIONS.md", "AGENTS.md", "CLAUDE.md", "CHANGELOG.md", "CONTRIBUTING.md",
        "SECURITY.md", "LICENSE.md", "**/README.md", "**/SKILL.md", "**/AGENTS.md",
    ],
}


def load_config(start: str) -> dict:
    """Merge DEFAULTS <- nearest .claude/guard.json (walking up) <- KZ_* env."""
    cfg = dict(DEFAULTS)
    d = os.path.abspath(start)
    while True:
        candidate = os.path.join(d, ".claude", "guard.json")
        if os.path.isfile(candidate):
            try:
                with open(candidate, encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    cfg.update(data)
            except (OSError, ValueError) as exc:  # a broken config must not silently vanish
                print(f"guard: ignoring unreadable {candidate}: {exc}", file=sys.stderr)
            break
        parent = os.path.dirname(d)
        if parent == d:
            break
        d = parent
    env = os.environ.get("KZ_TELEMETRY_DIR")
    if env:
        cfg["telemetry_dir"] = env
    env = os.environ.get("KZ_PROTECTED_BRANCHES")
    if env:
        cfg["protected_branches"] = [b.strip() for b in env.split(",") if b.strip()]
    env = os.environ.get("KZ_BOUNDARY")
    if env:
        cfg["boundary"] = env.strip()
    env = os.environ.get("KZ_SCRATCH_MD")
    if env:
        cfg["scratch_md_mode"] = env.strip()
    return cfg


def protected_branches(cfg: dict) -> set:
    v = cfg.get("protected_branches")
    if v is None:
        v = DEFAULTS["protected_branches"]
    return {str(b) for b in v}  # an explicit empty list means: no protected branch here


def telemetry_dir(cfg: dict) -> str:
    return os.path.expanduser(str(cfg.get("telemetry_dir") or DEFAULTS["telemetry_dir"]))


# ----------------------------------------------------------------------------
# Decisions
# ----------------------------------------------------------------------------

Decision = tuple[str, str]  # ("ask"|"deny", reason)
RANK = {"ask": 1, "deny": 2}


def respond(decision: Optional[Decision], event_name: str) -> int:
    """Print the decision in the shape both harnesses read; return the exit code."""
    if decision is None:
        return 0
    verdict, reason = decision
    payload = {
        "permissionDecision": verdict,
        "permissionDecisionReason": reason,
        "hookSpecificOutput": {
            "hookEventName": event_name,
            "permissionDecision": verdict,
            "permissionDecisionReason": reason,
        },
    }
    sys.stdout.write(json.dumps(payload) + "\n")
    sys.stdout.flush()
    if verdict == "deny":
        sys.stderr.write(reason + "\n")
        return 2
    return 0


def combine(decisions: list[Decision]) -> Optional[Decision]:
    """Strongest verdict wins; reasons of the winning class are joined."""
    if not decisions:
        return None
    top = max(RANK[d[0]] for d in decisions)
    reasons = [r for v, r in decisions if RANK[v] == top]
    verdict = "deny" if top == 2 else "ask"
    return verdict, " | ".join(dict.fromkeys(reasons))


# ----------------------------------------------------------------------------
# Rule: delete-guard (ported from ~/.claude/hooks/ask-on-delete.sh, owner rule
# 2026-09-24: never auto-approve deletions, scripts included, no exceptions)
# ----------------------------------------------------------------------------

_ASSIGN = r"[A-Za-z_][A-Za-z0-9_]*=\S*\s+"
SHELL_RE = (
    r"(^|[;&|(`]|\$\()\s*(" + _ASSIGN + r")*((sudo|env|exec|command|time|nohup|doas)\s+("
    + _ASSIGN + r")*)*(/bin/|/usr/bin/)?(rm|rmdir|unlink|trash|shred|truncate)(\s|$)"
)
FIND_RE = (
    r"find\s.*(-delete|-exec\s+(/bin/)?rm)|xargs(\s+\S+)*\s+(/bin/)?(rm|rmdir|unlink|trash)(\s|$)"
    r"|parallel(\s+\S+)*\s+(/bin/)?rm(\s|$)"
)
_GIT = r"git\s+(-C\s+\S+\s+)?"
GIT_RE = (
    _GIT + r"(rm|clean|reset|restore|filter-branch|filter-repo)(\s|$)"
    + r"|" + _GIT + r"checkout\s+(--|-f|--force)"
    + r"|" + _GIT + r"branch\s+.*(-D|-d|--delete)(\s|$)"
    + r"|" + _GIT + r"worktree\s+(remove|prune)"
    + r"|" + _GIT + r"push\s.*(--force|-f(\s|$)|--force-with-lease|--delete|\s:\S)"
    + r"|" + _GIT + r"stash\s+(drop|clear)"
    + r"|git\s+update-ref\s+-d|git\s+tag\s+(-d|--delete)"
)
TOOL_RE = (
    r"mise\s+(uninstall|prune)|npm\s+(uninstall|rm|un|r|unlink)(\s|$)|pnpm\s+(remove|rm|uninstall)"
    r"|yarn\s+remove|brew\s+(uninstall|remove|rm)|pip3?\s+uninstall|cargo\s+uninstall"
    r"|docker\s+(rm|rmi|system\s+prune|volume\s+(rm|prune)|image\s+prune|container\s+prune"
    r"|builder\s+prune|compose\s+(down|rm))|kubectl\s+delete|helm\s+(uninstall|delete)|dropdb"
    r"|prisma\s+migrate\s+reset|--force-reset|(DROP|drop)\s+(TABLE|DATABASE|SCHEMA|table|database|schema)"
    r"|(TRUNCATE|truncate)\s|(DELETE|delete)\s+(FROM|from)\s|rclone\s+(delete|purge|sync)|rsync\s.*--delete"
)
CODE_RE = (
    r"os\.(remove|unlink|rmdir|removedirs)|shutil\.rmtree|\.unlink\(|\.rmdir\(|send2trash"
    r"|fs\.(rm|rmSync|unlink|unlinkSync|rmdir|rmdirSync)|fsPromises\.(rm|unlink|rmdir)|rimraf|del\s*\("
    r"|remove_dir_all|remove_file|std::fs::remove|File\.(delete|unlink)|FileUtils\.(rm|remove)"
    r"|Remove-Item|Directory\.Delete|(^|\s)del\s+/[sq]|(^|\s)rd\s+/s"
)
DELETE_RE = re.compile("|".join([SHELL_RE, FIND_RE, GIT_RE, TOOL_RE, CODE_RE]), re.MULTILINE)
SCRIPT_RE = re.compile(
    r"(python3?|node|bun|deno|bash|sh|zsh|tsx|ts-node|ruby|perl|php)\s+(-\S+\s+)*(\S+\.(py|js|mjs|cjs|ts|sh|zsh|bash|rb|pl|php))"
)
DELETE_MSG = (
    "Deletion guard (owner rule: never auto-approve deletions, scripts included): {what}. "
    "Ask the owner explicitly."
)


def rule_delete_guard(ev: Event, cfg: dict) -> Optional[Decision]:
    if ev.event != "PreToolUse" or ev.kind != "shell" or not ev.command:
        return None
    if DELETE_RE.search(ev.command):
        return "ask", DELETE_MSG.format(what="command contains a delete/discard pattern")
    for m in SCRIPT_RE.finditer(ev.command):
        script = m.group(3)
        p = script if os.path.isabs(script) else os.path.join(ev.cwd, script)
        try:
            with open(p, encoding="utf-8", errors="replace") as fh:
                if DELETE_RE.search(fh.read()):
                    return "ask", DELETE_MSG.format(
                        what=f"script {script} contains a delete/discard pattern"
                    )
        except OSError:
            continue  # not a readable file: nothing to scan
    return None



# ----------------------------------------------------------------------------
# Shell helpers
# ----------------------------------------------------------------------------

_SEP_RE = re.compile(r"\|\||&&|[;|]|\n")
_WRAPPERS = {"sudo", "env", "command", "exec", "time", "nohup", "doas", "builtin"}
_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")


def tokens(text: str) -> list[str]:
    try:
        return shlex.split(text, posix=True)
    except ValueError:
        return text.split()


def segments(command: str) -> list[list[str]]:
    """Token lists for each simple command of a compound line, wrappers and assignments stripped."""
    out = []
    for part in _SEP_RE.split(command):
        toks = tokens(part)
        while toks and (_ASSIGN_RE.match(toks[0]) or toks[0] in _WRAPPERS):
            toks = toks[1:]
            while toks and toks[0].startswith("-") and toks[0] != "--":
                toks = toks[1:]
        if toks:
            out.append(toks)
    return out


def _expand(tok: str, cwd: str) -> str:
    t = os.path.expanduser(tok.replace("$HOME", "~"))
    return t if os.path.isabs(t) else os.path.normpath(os.path.join(cwd, t))


_HEREDOC_RE = re.compile(
    r"<<-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1[^\n]*\n(.*?)(?:\n\2(?:\n|$)|\Z)", re.DOTALL
)


def strip_heredocs(command: str) -> str:
    """Drop here-document bodies: they are data for a command, not commands (the delete-guard keeps them)."""
    return _HEREDOC_RE.sub(lambda m: m.group(0)[: m.start(3) - m.start(0)], command)


# ----------------------------------------------------------------------------
# Secret-bearing paths (AGENTS.md rule 6: secrets in a vault, never in code, repo or state)
# ----------------------------------------------------------------------------

_SECRET_NAME_RE = re.compile(
    r"^(\.env(\..+)?|.*\.(pem|key|p12|pfx|jks|keystore|tfstate|tfstate\.backup)"
    r"|id_(rsa|dsa|ecdsa|ed25519)|\.netrc|\.pypirc|\.git-credentials)$"
)
_EXAMPLE_RE = re.compile(r"\.(example|sample|template|dist)$")
_TFVARS_RE = re.compile(r"\.tfvars$")
_SECRET_IN_DIR = {
    (".aws", "credentials"): "~/.aws/credentials",
    (".kube", "config"): "~/.kube/config",
    ("gh", "hosts.yml"): "~/.config/gh/hosts.yml",
    (".docker", "config.json"): "~/.docker/config.json",
}


def secret_class(path: Optional[str]) -> Optional[str]:
    """'secret' (deny on write, ask on read), 'tfvars' (ask on write), or None."""
    if not path:
        return None
    base = os.path.basename(path.rstrip("/"))
    parent = os.path.basename(os.path.dirname(path))
    if _EXAMPLE_RE.search(base):
        return None
    if (parent, base) in _SECRET_IN_DIR:
        return "secret"
    if _SECRET_NAME_RE.match(base):
        return "secret"
    if _TFVARS_RE.search(base):
        return "tfvars"
    return None


SECRET_WRITE_MSG = (
    "Secret boundary (AGENTS.md rule 6): {path} is a secret-bearing file; it is never written by the agent. "
    "Keep values in the vault or the environment; a *.example with names only is fine."
)
SECRET_READ_MSG = (
    "Secret boundary (AGENTS.md rule 6): {path} may hold credentials. Confirm this read is intended; "
    "prefer names-only samples or redacted copies."
)
TFVARS_MSG = (
    "{path} is a tfvars file; such files often carry secrets. "
    "Confirm it holds no secret values before editing."
)


def rule_secret_write(ev: Event, cfg: dict) -> Optional[Decision]:
    if ev.event != "PreToolUse" or ev.kind not in ("write", "edit"):
        return None
    cls = secret_class(ev.abspath())
    if cls == "secret":
        return "deny", SECRET_WRITE_MSG.format(path=ev.path)
    if cls == "tfvars":
        return "ask", TFVARS_MSG.format(path=ev.path)
    return None


def rule_secret_read(ev: Event, cfg: dict) -> Optional[Decision]:
    if ev.event != "PreToolUse" or ev.kind != "read":
        return None
    if secret_class(ev.abspath()) == "secret":
        return "ask", SECRET_READ_MSG.format(path=ev.path)
    return None


_REDIRECT_RE = re.compile(r"(?<![<>])>{1,2}\s*([^\s;&|]+)")
_WRITERS_LAST = {"cp", "mv", "install", "scp", "rsync", "ln"}
_WRITERS_ALL = {"tee", "truncate", "touch", "chmod", "chown"}


def rule_secret_shell(ev: Event, cfg: dict) -> Optional[Decision]:
    if ev.event != "PreToolUse" or ev.kind != "shell" or not ev.command:
        return None
    writes, reads = [], []
    command = strip_heredocs(ev.command)
    for target in _REDIRECT_RE.findall(command):
        target = target.strip("\"'`,;)")
        if secret_class(_expand(target, ev.cwd)) == "secret":
            writes.append(target)
    for seg in segments(command):
        head = os.path.basename(seg[0])
        paths = [t for t in seg[1:] if not t.startswith("-") and t != "--"]
        targets: list[str] = []
        if head in _WRITERS_LAST and paths:
            targets = paths[-1:]
        elif head in _WRITERS_ALL:
            targets = paths
        elif head == "sed" and any(t.startswith("-i") for t in seg):
            targets = paths
        elif head == "git" and len(seg) > 1 and seg[1] in ("add", "stage"):
            targets = paths[1:] if paths and paths[0] in ("add", "stage") else paths
        for t in targets:
            if secret_class(_expand(t, ev.cwd)) == "secret":
                writes.append(t)
        for t in paths:
            if t not in targets and secret_class(_expand(t, ev.cwd)) == "secret":
                reads.append(t)
    if writes:
        return "deny", SECRET_WRITE_MSG.format(path=", ".join(dict.fromkeys(writes)))
    if reads:
        return "ask", SECRET_READ_MSG.format(path=", ".join(dict.fromkeys(reads)))
    return None


# ----------------------------------------------------------------------------
# git-guard: no force push, no push to a protected branch, no --no-verify
# ----------------------------------------------------------------------------

_GIT_GLOBAL_WITH_VALUE = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}
_PUSH_OPT_WITH_VALUE = {"-o", "--push-option", "--receive-pack", "--exec", "--repo", "--recurse-submodules"}
_FORCE_FLAGS = {"-f", "--force", "--force-with-lease", "--force-if-includes"}
GIT_MSG = (
    "git-guard: {what}. Work on a branch and open a PR; "
    "force pushes and hook bypasses are never auto-approved."
)


def _git_subcommand(seg: list[str]) -> tuple[Optional[str], list[str]]:
    if not seg or os.path.basename(seg[0]) != "git":
        return None, []
    i = 1
    while i < len(seg) and seg[i].startswith("-"):
        if seg[i] in _GIT_GLOBAL_WITH_VALUE:
            i += 2
        else:
            i += 1
    if i >= len(seg):
        return None, []
    return seg[i], seg[i + 1 :]


def current_branch(cwd: str) -> Optional[str]:
    """Checked-out branch name, also on an unborn branch; None when detached or not a repo."""
    for args in (["symbolic-ref", "--short", "-q", "HEAD"], ["rev-parse", "--abbrev-ref", "HEAD"]):
        try:
            r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=3)
        except (OSError, subprocess.SubprocessError):
            return None
        name = r.stdout.strip()
        if r.returncode == 0 and name and name != "HEAD":
            return name
    return None


def rule_git_guard(ev: Event, cfg: dict) -> Optional[Decision]:
    if ev.event != "PreToolUse" or ev.kind != "shell" or not ev.command:
        return None
    protected = protected_branches(cfg)
    for seg in segments(strip_heredocs(ev.command)):
        sub, rest = _git_subcommand(seg)
        if sub is None:
            continue
        if "--no-verify" in rest or (sub == "commit" and "-n" in rest):
            return "deny", GIT_MSG.format(what=f"`git {sub} --no-verify` skips the commit gate")
        if sub != "push":
            continue
        if any(t in _FORCE_FLAGS or t.startswith("--force-with-lease=") for t in rest):
            return "deny", GIT_MSG.format(what="force push")
        if "--all" in rest or "--mirror" in rest:
            return "deny", GIT_MSG.format(what="`git push --all/--mirror` can rewrite a protected branch")
        positional: list[str] = []
        skip = False
        for t in rest:
            if skip:
                skip = False
                continue
            if t in _PUSH_OPT_WITH_VALUE:
                skip = True
                continue
            if t.startswith("-"):
                continue
            positional.append(t)
        refspecs = positional[1:]
        if not refspecs:
            branch = current_branch(ev.cwd)
            if branch in protected:
                return "deny", GIT_MSG.format(what=f"push to protected branch '{branch}'")
            continue
        for r in refspecs:
            if r.startswith("+"):
                return "deny", GIT_MSG.format(what=f"force refspec {r}")
            dest = r.split(":", 1)[1] if ":" in r else r
            if dest.startswith("refs/heads/"):
                dest = dest[len("refs/heads/") :]
            if dest == "HEAD":
                dest = current_branch(ev.cwd) or dest
            if dest in protected:
                return "deny", GIT_MSG.format(what=f"push to protected branch '{dest}'")
    return None


# ----------------------------------------------------------------------------
# deploy-ask: anything that changes a live environment needs an explicit yes
# ----------------------------------------------------------------------------

_DEPLOY_PATTERNS = [
    (
        r"(terraform|tofu)\s+(apply|destroy|import|taint|untaint|state\s+(rm|mv|push))",
        "terraform/tofu changes state",
    ),
    (
        r"kubectl\s+(apply|create|delete|rollout|drain|cordon|uncordon|scale|patch|replace|edit|exec)",
        "kubectl changes the cluster",
    ),
    (r"helm\s+(install|upgrade|uninstall|delete|rollback)", "helm changes a release"),
    (r"docker\s+push|docker\s+compose\s+push", "pushes an image"),
    (r"gh\s+workflow\s+run|gh\s+release\s+(create|delete|edit|upload)", "triggers a workflow or release"),
    (r"az\s+deployment|az\s+\S+(\s+\S+)*\s+(delete|create)", "az changes resources"),
    (
        r"aws\s+cloudformation\s+(deploy|create-stack|update-stack|delete-stack|execute-change-set)",
        "CloudFormation",
    ),
    (r"aws\s+s3\s+(rm|rb)|aws\s+s3\s+sync\s.*--delete", "aws s3 deletes"),
    (r"hcloud\s+server\s+(create|delete|rebuild|poweroff|reset|shutdown)", "hcloud server lifecycle"),
    (r"pvesh\s+(create|set|delete)|qm\s+(destroy|stop|shutdown|reset)", "Proxmox changes a guest"),
    (r"pulumi\s+(up|destroy)|cdk\s+(deploy|destroy)", "pulumi/cdk deploys"),
    (r"ansible-playbook", "ansible-playbook changes hosts"),
    (r"flux\s+(uninstall|suspend)", "flux changes reconciliation"),
]
_DEPLOY_RES = [
    (re.compile(r"(^|[;&|(`]|\$\()\s*(sudo\s+)?(" + p + r")(\s|$)", re.MULTILINE), label)
    for p, label in _DEPLOY_PATTERNS
]
_DRY_RE = re.compile(r"--dry-run|--check(\s|$)|\s--diff(\s|$)|\s(plan|validate|template|lint|diff)(\s|$)")
DEPLOY_MSG = (
    "Deploy/apply boundary: {what}. Needs an explicit yes (AGENTS.md: terraform plan / kubectl diff first)."
)


def rule_deploy_ask(ev: Event, cfg: dict) -> Optional[Decision]:
    if ev.event != "PreToolUse" or ev.kind != "shell" or not ev.command:
        return None
    for part in _SEP_RE.split(strip_heredocs(ev.command)):
        if _DRY_RE.search(part):
            continue
        for rx, label in _DEPLOY_RES:
            if rx.search(" " + part.strip()) or rx.search(part):
                return "ask", DEPLOY_MSG.format(what=label)
    return None


# ----------------------------------------------------------------------------
# egress-guard: inside a client boundary, other-vendor LLM tools need a yes
# ----------------------------------------------------------------------------

_OTHER_LLM_CLIS = {"agy", "gemini", "codex", "llm", "openai", "ollama", "aider", "cursor-agent"}
_LLM_HOSTS_RE = re.compile(
    r"api\.openai\.com|generativelanguage\.googleapis\.com|openrouter\.ai|api\.mistral\.ai|api\.together\.xyz|api\.anthropic\.com"
)
EGRESS_MSG = (
    "Client boundary (KZ_BOUNDARY=client): {what} would send material to another vendor's endpoint. "
    "Only the agreed endpoint; use the egress screen for anything that must leave the machine."
)


def rule_egress_guard(ev: Event, cfg: dict) -> Optional[Decision]:
    if ev.event != "PreToolUse" or ev.kind != "shell" or not ev.command:
        return None
    if str(cfg.get("boundary") or "own") != "client":
        return None
    for seg in segments(strip_heredocs(ev.command)):
        head = os.path.basename(seg[0])
        if head in _OTHER_LLM_CLIS:
            return "ask", EGRESS_MSG.format(what=f"`{head}`")
        if head in ("curl", "wget", "http", "https", "xh") and _LLM_HOSTS_RE.search(" ".join(seg)):
            return "ask", EGRESS_MSG.format(what=f"`{head}` to an LLM API host")
    return None

# ----------------------------------------------------------------------------
# scratch-md: a NEW markdown file outside the documented homes is a smell (plan step 1.5)
# ----------------------------------------------------------------------------


def git_root(start_dir: str) -> Optional[str]:
    d = os.path.abspath(start_dir)
    while True:
        if os.path.exists(os.path.join(d, ".git")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


SCRATCH_MSG = (
    "Scratch-markdown guard: {rel} would be a new .md outside the documented homes ({homes}, …). "
    "Findings belong in the reply, the PR body or the tracker; documentation goes under docs/. "
    "Say yes only if this file is meant to stay."
)


def rule_scratch_md(ev: Event, cfg: dict) -> Optional[Decision]:
    if ev.event != "PreToolUse" or ev.kind != "write":
        return None
    mode = str(cfg.get("scratch_md_mode") or "ask")
    if mode == "off":
        return None
    p = ev.abspath()
    if not p or not p.lower().endswith((".md", ".markdown")) or os.path.exists(p):
        return None
    root = git_root(os.path.dirname(p))
    if root is None:
        return None
    rel = os.path.relpath(p, root).replace(os.sep, "/")
    allow = cfg.get("scratch_md_allow") or DEFAULTS["scratch_md_allow"]
    base = os.path.basename(rel)
    for pat in allow:
        if pat.endswith("/") and rel.startswith(pat):
            return None
        if pat.startswith("**/") and base == pat[3:]:
            return None
        if rel == pat:
            return None
    verdict = "deny" if mode == "deny" else "ask"
    return verdict, SCRATCH_MSG.format(rel=rel, homes=", ".join(allow[:4]))


# ----------------------------------------------------------------------------
# Registry
# ----------------------------------------------------------------------------

Rule = Callable[[Event, dict], Optional[Decision]]
RULES: dict[str, Rule] = {
    "delete-guard": rule_delete_guard,
    "secret-write": rule_secret_write,
    "secret-read": rule_secret_read,
    "secret-shell": rule_secret_shell,
    "git-guard": rule_git_guard,
    "deploy-ask": rule_deploy_ask,
    "egress-guard": rule_egress_guard,
    "scratch-md": rule_scratch_md,
}
PRE_RULES = list(RULES)


# ----------------------------------------------------------------------------
# Capture (plan step 1.3): record what each harness really sends
# ----------------------------------------------------------------------------

_SECRET_RES = [
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"AGE-SECRET-KEY-1[0-9A-Z]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
]


def redact(obj):
    home = os.path.expanduser("~")
    if isinstance(obj, dict):
        return {k: redact(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [redact(v) for v in obj]
    if isinstance(obj, str):
        s = obj.replace(home, "~") if home and home != "/" else obj
        for rx in _SECRET_RES:
            s = rx.sub("<redacted>", s)
        return s
    return obj


def capture(raw: dict, cfg: dict) -> int:
    ev = Event(raw)
    out_dir = os.path.join(telemetry_dir(cfg), "captures", ev.harness)
    try:
        os.makedirs(out_dir, exist_ok=True)
        stamp = _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        name = f"{ev.event or 'event'}-{ev.tool or 'none'}-{stamp}.json"
        with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
            json.dump(redact(raw), fh, indent=2, sort_keys=True)
            fh.write("\n")
    except OSError as exc:
        print(f"guard: capture failed: {exc}", file=sys.stderr)
    return 0


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------

def _read_event() -> dict:
    data = sys.stdin.read()
    if not data.strip():
        raise ValueError("empty stdin; expected one JSON hook event")
    obj = json.loads(data)
    if not isinstance(obj, dict):
        raise ValueError("hook event must be a JSON object")
    return obj


def run_hook(target: str, wrapper: Optional[str]) -> int:
    raw = _read_event()
    cfg = load_config(str(raw.get("cwd") or os.getcwd()))
    if target == "capture":
        return capture(raw, cfg)
    ev = Event(raw)
    # One Copilot path only: VS Code reads both .claude/settings.json and
    # .github/hooks; the github wrapper does the work there.
    if wrapper == "claude" and ev.harness == "copilot":
        return 0
    names = PRE_RULES if target == "pre" else [target]
    decisions: list[Decision] = []
    for name in names:
        rule = RULES.get(name)
        if rule is None:
            raise ValueError(f"unknown rule: {name}")
        d = rule(ev, cfg)
        if d:
            decisions.append(d)
    return respond(combine(decisions), ev.event or "PreToolUse")


def main(argv: list[str]) -> int:
    args = list(argv)
    wrapper = None
    if "--wrapper" in args:
        i = args.index("--wrapper")
        wrapper = args[i + 1] if i + 1 < len(args) else None
        del args[i : i + 2]
    if not args or args[0] in ("help", "-h", "--help"):
        print(__doc__.strip())
        return 0
    if args[0] == "version":
        print(VERSION)
        return 0
    if args[0] == "rules":
        for n in RULES:
            print(n)
        return 0
    if args[0] == "hook" and len(args) >= 2:
        try:
            return run_hook(args[1], wrapper)
        except Exception as exc:  # the guard failing is reported, never hidden
            print(f"guard: error: {exc}", file=sys.stderr)
            return 1
    print(__doc__.strip(), file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
