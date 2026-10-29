import json
import os
import pathlib
import subprocess
import sys

FIX = pathlib.Path(__file__).parent / "fixtures"


def run(guard_path, args, payload):
    data = payload if isinstance(payload, (bytes, str)) else json.dumps(payload)
    raw = data.encode() if isinstance(data, str) else data
    return subprocess.run([sys.executable, guard_path, *args], input=raw, capture_output=True)


def _bash(harness, cmd):
    shape = "claude/PreToolUse-Bash.json" if harness == "claude" else "copilot/PreToolUse-bash.json"
    d = json.loads((FIX / "_shapes" / shape).read_text())
    d["tool_input"] = {"command": cmd}
    return d


def test_ask_exit_0_with_both_decision_keys(guard_path):
    r = run(guard_path, ["hook", "pre"], _bash("claude", "rm -rf build"))
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["permissionDecision"] == "ask"
    assert out["hookSpecificOutput"]["permissionDecision"] == "ask"
    assert out["hookSpecificOutput"]["hookEventName"] == "PreToolUse"
    assert out["permissionDecisionReason"] == out["hookSpecificOutput"]["permissionDecisionReason"]


def test_allow_is_silent(guard_path):
    r = run(guard_path, ["hook", "pre"], _bash("claude", "git status"))
    assert r.returncode == 0 and r.stdout == b"" and r.stderr == b""


def test_deny_exit_2_json_and_stderr(guard, capsys):
    code = guard.respond(("deny", "nope"), "PreToolUse")
    captured = capsys.readouterr()
    assert code == 2
    assert json.loads(captured.out)["permissionDecision"] == "deny"
    assert captured.err.strip() == "nope"


def test_combine_prefers_deny_and_joins_reasons(guard):
    assert guard.combine([]) is None
    assert guard.combine([("ask", "a"), ("ask", "a"), ("ask", "b")]) == ("ask", "a | b")
    assert guard.combine([("ask", "a"), ("deny", "d")]) == ("deny", "d")


def test_copilot_event_through_claude_wrapper_is_a_noop(guard_path):
    r = run(guard_path, ["hook", "pre", "--wrapper", "claude"], _bash("copilot", "rm -rf build"))
    assert r.returncode == 0 and r.stdout == b""
    r = run(guard_path, ["hook", "pre", "--wrapper", "github"], _bash("copilot", "rm -rf build"))
    assert r.returncode == 0 and json.loads(r.stdout)["permissionDecision"] == "ask"
    r = run(guard_path, ["hook", "pre", "--wrapper", "claude"], _bash("claude", "rm -rf build"))
    assert json.loads(r.stdout)["permissionDecision"] == "ask"


def test_single_rule_and_unknown_rule(guard_path):
    r = run(guard_path, ["hook", "delete-guard"], _bash("claude", "rm -rf build"))
    assert r.returncode == 0 and b"ask" in r.stdout
    r = run(guard_path, ["hook", "no-such-rule"], _bash("claude", "ls"))
    assert r.returncode == 1 and b"unknown rule" in r.stderr and r.stdout == b""


def test_capture_writes_redacted_file(guard_path, tmp_path, monkeypatch):
    monkeypatch.setenv("KZ_TELEMETRY_DIR", str(tmp_path / "t"))
    d = _bash("claude", "echo ghp_abcdefghijklmnopqrstuvwxyz0123 > /dev/null")
    env = {**os.environ, "KZ_TELEMETRY_DIR": str(tmp_path / "t")}
    r = subprocess.run([sys.executable, guard_path, "hook", "capture"], input=json.dumps(d).encode(),
                       capture_output=True, env=env)
    assert r.returncode == 0 and r.stdout == b""
    files = list((tmp_path / "t" / "captures" / "claude").glob("PreToolUse-Bash-*.json"))
    assert len(files) == 1
    text = files[0].read_text()
    assert "ghp_" not in text and "<redacted>" in text


def test_help_version_rules(guard, guard_path):
    assert run(guard_path, ["version"], "").stdout.strip().decode() == guard.VERSION
    assert b"delete-guard" in run(guard_path, ["rules"], "").stdout
    assert b"Usage" in run(guard_path, ["help"], "").stdout
