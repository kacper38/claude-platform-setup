import json
import pathlib
import subprocess
import sys

import pytest

FIX = pathlib.Path(__file__).parent / "fixtures"


def _cases():
    for harness in ("claude", "copilot"):
        for decision in ("ask", "allow"):
            for f in sorted((FIX / "delete-guard" / harness / decision).glob("*.json")):
                yield harness, decision, f


@pytest.mark.parametrize("harness,decision,path", list(_cases()), ids=lambda x: getattr(x, "name", str(x)))
def test_fixture(guard, harness, decision, path):
    ev = guard.Event(json.loads(path.read_text()))
    assert ev.harness == harness
    got = guard.rule_delete_guard(ev, {})
    if decision == "allow":
        assert got is None, f"{path.name}: unexpected {got}"
    else:
        assert got is not None and got[0] == "ask", f"{path.name}: expected ask, got {got}"
        assert "never auto-approve deletions" in got[1]


def test_script_invoked_by_path_is_scanned(guard, tmp_path):
    (tmp_path / "cleanup.py").write_text("import shutil\nshutil.rmtree('build')\n")
    (tmp_path / "ok.py").write_text("print('hello')\n")
    base = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": str(tmp_path)}
    bad = guard.Event({**base, "tool_input": {"command": "python3 cleanup.py --dry-run"}})
    good = guard.Event({**base, "tool_input": {"command": "python3 ok.py"}})
    missing = guard.Event({**base, "tool_input": {"command": "python3 nope.py"}})
    assert guard.rule_delete_guard(bad, {})[1].startswith("Deletion guard")
    assert "script cleanup.py" in guard.rule_delete_guard(bad, {})[1]
    assert guard.rule_delete_guard(good, {}) is None
    assert guard.rule_delete_guard(missing, {}) is None


def test_only_shell_pretooluse(guard):
    post = guard.Event(
        {"hook_event_name": "PostToolUse", "tool_name": "Bash", "tool_input": {"command": "rm -rf x"}}
    )
    write = guard.Event(
        {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "rm", "content": "rm -rf x"},
        }
    )
    assert guard.rule_delete_guard(post, {}) is None
    assert guard.rule_delete_guard(write, {}) is None


@pytest.mark.parametrize("path", sorted((FIX / "_crash").iterdir()), ids=lambda p: p.name)
def test_crash_fixtures_exit_1_with_nothing_on_stdout(guard_path, path):
    r = subprocess.run(
        [sys.executable, guard_path, "hook", "pre"], input=path.read_bytes(), capture_output=True
    )
    assert r.returncode == 1, r
    assert r.stdout == b""
    assert b"guard: error" in r.stderr
