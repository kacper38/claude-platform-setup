#!/usr/bin/env python3
"""test-guard — PostToolUse feedback when an edit weakens the test suite (plan step 3.7).

After a Write/Edit/Bash that touched a test file (the written path, or a test path named in the
command) it runs tools/testguard/check-test-tampering.sh --worktree and hands the findings back to
the agent. Claude Code reads `decision: block` + `reason`; Copilot reads `additionalContext`.
Exit 0 always: the tool already ran, and a guard that cannot run (no git, no base) must stay
silent rather than add noise. CI runs the script itself (.github/workflows/ci.yml, job `guards`).

  testguard.py hook        stdin: one PostToolUse event, Claude Code or Copilot shape
Env: BASE_REF (default origin/main) reaches the script unchanged.
"""
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "check-test-tampering.sh")
TIMEOUT = 8
MAX_CHARS = 4000
_TEST_FILE_RE = re.compile(r"(^|/)(test_[^/\s]*\.py|[^/\s]*_test\.py|[^/\s]+\.(spec|test)\.[^/\s]+)$")
_TEST_IN_COMMAND_RE = re.compile(
    r"(^|[\s/'\"=])(tests?(/|\s|$)|test_[\w.-]*\.py|[\w.-]*_test\.py|[\w.-]+\.(spec|test)\.\w+)")


def is_copilot(raw: dict) -> bool:
    """Same tell the guard uses: Copilot payloads carry `timestamp` or camelCase keys."""
    return "timestamp" in raw or "toolName" in raw or "toolArgs" in raw


def tool_args(raw: dict) -> dict:
    """tool_input (Claude Code, VS Code format) or toolArgs (Copilot CLI), which may arrive JSON-encoded."""
    args = raw.get("tool_input") if "tool_input" in raw else raw.get("toolArgs")
    if isinstance(args, str):
        try:
            args = json.loads(args)
        except ValueError:
            args = {}
    return args if isinstance(args, dict) else {}

def touches_tests(path: str, command: str) -> bool:
    if path and _TEST_FILE_RE.search(path.replace("\\", "/")):
        return True
    return bool(command and _TEST_IN_COMMAND_RE.search(command))


def run_guard(cwd: str) -> str:
    """The script's findings, '' when the tree is clean or the guard itself could not run."""
    try:
        r = subprocess.run(["bash", SCRIPT, "--worktree"], cwd=cwd, capture_output=True, text=True,
                           timeout=TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return ""
    text = r.stderr.strip()
    return text if "(check-test-tampering)" in text else ""  # anything else is git or bash complaining


def feedback(text: str, copilot: bool) -> dict:
    msg = "test-guard: " + text[:MAX_CHARS]
    if copilot:
        return {"additionalContext": msg}
    return {"decision": "block", "reason": msg}


def hook(stdin, out) -> int:
    try:
        raw = json.loads(stdin.read() or "{}")
    except ValueError:
        return 0
    if not isinstance(raw, dict):
        return 0
    args = tool_args(raw)
    path = next((args[k] for k in ("file_path", "path", "filePath", "notebook_path") if isinstance(args.get(k), str)),
                "")
    command = args.get("command") if isinstance(args.get("command"), str) else ""
    if not touches_tests(path, command):
        return 0
    cwd = os.path.dirname(os.path.expanduser(path)) if path else ""
    if not os.path.isdir(cwd):
        cwd = str(raw.get("cwd") or os.getcwd())
    if not os.path.isdir(cwd):
        return 0
    text = run_guard(cwd)
    if text:
        out.write(json.dumps(feedback(text, is_copilot(raw))) + "\n")
    return 0


def main(argv: list, stdin=None, out=None) -> int:
    stdin, out = stdin or sys.stdin, out or sys.stdout
    if argv[:1] == ["hook"]:
        return hook(stdin, out)
    out.write(__doc__.strip() + "\n")
    return 0 if argv[:1] in (["help"], ["-h"], ["--help"]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
