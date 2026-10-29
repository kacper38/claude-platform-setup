"""protected-branch needs real repositories: the file's own checkout decides, not the session's cwd."""
import subprocess


def _repo(tmp_path, branch):
    subprocess.run(["git", "init", "-q", "-b", branch, str(tmp_path)], check=True)
    return str(tmp_path)


def _ev(guard, cwd, tool, tool_input):
    return guard.Event({"hook_event_name": "PreToolUse", "tool_name": tool, "cwd": cwd, "tool_input": tool_input})


def _judge(guard, cwd, tool, tool_input, cfg=None):
    return guard.rule_protected_branch(_ev(guard, cwd, tool, tool_input), cfg or guard.DEFAULTS)


def test_edit_on_protected_branch_denied_both_harnesses(guard, tmp_path):
    cwd = _repo(tmp_path, "main")
    got = _judge(guard, cwd, "Edit", {"file_path": "README.md", "old_string": "a", "new_string": "b"})
    assert got and got[0] == "deny" and "'main'" in got[1] and "README.md" in got[1]
    got = _judge(guard, cwd, "Write", {"file_path": f"{cwd}/src/new.py", "content": "x"})
    assert got and got[0] == "deny"
    raw = {"hook_event_name": "PreToolUse", "tool_name": "create", "cwd": cwd, "timestamp": "t",
           "tool_input": {"path": "x.py", "file_text": "x"}}
    assert guard.rule_protected_branch(guard.Event(raw), guard.DEFAULTS)[0] == "deny"


def test_feature_branch_and_outside_repo_allowed(guard, tmp_path):
    repo = _repo(tmp_path / "repo", "step-2")
    assert guard.rule_protected_branch(_ev(guard, repo, "Edit", {"file_path": "README.md"}), guard.DEFAULTS) is None
    (tmp_path / "notes").mkdir()
    ev = _ev(guard, repo, "Write", {"file_path": str(tmp_path / "notes" / "x.md"), "content": "x"})
    assert guard.rule_protected_branch(ev, guard.DEFAULTS) is None, "a file outside any repo is not judged"


def test_path_scoped_to_the_files_repo(guard, tmp_path):
    on_main = _repo(tmp_path / "a", "main")
    on_feature = _repo(tmp_path / "b", "feature")
    ev = _ev(guard, on_feature, "Edit", {"file_path": f"{on_main}/README.md"})
    assert guard.rule_protected_branch(ev, guard.DEFAULTS)[0] == "deny", "the file's checkout decides"
    ev = _ev(guard, on_main, "Edit", {"file_path": f"{on_feature}/README.md"})
    assert guard.rule_protected_branch(ev, guard.DEFAULTS) is None


def test_git_internals_not_judged(guard, tmp_path):
    cwd = _repo(tmp_path, "main")
    ev = _ev(guard, cwd, "Write", {"file_path": f"{cwd}/.git/COMMIT_EDITMSG", "content": "x"})
    assert guard.rule_protected_branch(ev, guard.DEFAULTS) is None


def test_commit_on_protected_branch_denied(guard, tmp_path):
    cwd = _repo(tmp_path / "repo", "main")
    got = _judge(guard, cwd, "Bash", {"command": "git add -A && git commit -m 'x'"})
    assert got and got[0] == "deny" and "git commit" in got[1]
    assert _judge(guard, cwd, "Bash", {"command": "git status && git diff"}) is None
    elsewhere = str(tmp_path / "elsewhere")
    (tmp_path / "elsewhere").mkdir()
    got = _judge(guard, elsewhere, "Bash", {"command": f"git -C {cwd} commit -m x"})
    assert got and got[0] == "deny"
    assert _judge(guard, elsewhere, "Bash", {"command": "git commit -m x"}) is None


def test_protected_set_from_config(guard, tmp_path):
    cwd = _repo(tmp_path, "release")
    ev = _ev(guard, cwd, "Edit", {"file_path": "x.py"})
    assert guard.rule_protected_branch(ev, guard.DEFAULTS) is None
    assert guard.rule_protected_branch(ev, {**guard.DEFAULTS, "protected_branches": ["release"]})[0] == "deny"
    assert guard.rule_protected_branch(ev, {**guard.DEFAULTS, "protected_branches": []}) is None
