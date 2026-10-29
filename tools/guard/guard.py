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
import sys
from typing import Callable, Optional

VERSION = "0.1.0"

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
    return cfg


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
# Registry
# ----------------------------------------------------------------------------

Rule = Callable[[Event, dict], Optional[Decision]]
RULES: dict[str, Rule] = {
    "delete-guard": rule_delete_guard,
}
PRE_RULES = ["delete-guard"]


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
