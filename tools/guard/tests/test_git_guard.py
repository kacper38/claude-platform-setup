"""git-guard cases that need a real repository (the checked-out branch decides)."""
import subprocess


def _repo(tmp_path, branch):
    subprocess.run(["git", "init", "-q", "-b", branch, str(tmp_path)], check=True)
    return str(tmp_path)


def _ev(guard, cwd, command):
    raw = {"hook_event_name": "PreToolUse", "tool_name": "Bash", "cwd": cwd, "tool_input": {"command": command}}
    return guard.Event(raw)


def test_bare_push_on_protected_branch_denied(guard, tmp_path):
    cwd = _repo(tmp_path, "main")
    got = guard.rule_git_guard(_ev(guard, cwd, "git push"), guard.DEFAULTS)
    assert got and got[0] == "deny" and "protected branch 'main'" in got[1]
    got = guard.rule_git_guard(_ev(guard, cwd, "git push origin HEAD"), guard.DEFAULTS)
    assert got and got[0] == "deny"


def test_bare_push_on_feature_branch_allowed(guard, tmp_path):
    cwd = _repo(tmp_path, "feature/x")
    assert guard.rule_git_guard(_ev(guard, cwd, "git push"), guard.DEFAULTS) is None
    assert guard.rule_git_guard(_ev(guard, cwd, "git push -u origin HEAD"), guard.DEFAULTS) is None


def test_protected_set_is_configurable(guard, tmp_path):
    cwd = _repo(tmp_path, "release")
    cfg = {**guard.DEFAULTS, "protected_branches": ["main", "release"]}
    assert guard.rule_git_guard(_ev(guard, cwd, "git push"), cfg)[0] == "deny"
    assert guard.rule_git_guard(_ev(guard, cwd, "git push origin feature:main"), {"protected_branches": []}) is None


def test_env_override(guard, monkeypatch, tmp_path):
    monkeypatch.setenv("KZ_PROTECTED_BRANCHES", "trunk, main")
    cfg = guard.load_config(str(tmp_path))
    assert guard.protected_branches(cfg) == {"trunk", "main"}
    monkeypatch.setenv("KZ_BOUNDARY", "client")
    assert guard.load_config(str(tmp_path))["boundary"] == "client"


def test_outside_a_repo_bare_push_is_not_judged(guard, tmp_path):
    assert guard.rule_git_guard(_ev(guard, str(tmp_path), "git push"), guard.DEFAULTS) is None


def test_heredoc_bodies_are_data(guard):
    body = "cat > notes.md <<'EOF'\nrun: echo X=1 > .env then git push --force\nEOF"
    assert guard.strip_heredocs(body) == "cat > notes.md <<'EOF'\n"
    assert guard.strip_heredocs("tee -a .env.local <<< 'X=1'") == "tee -a .env.local <<< 'X=1'"
    two = "cat <<A\nx\nA\necho mid\ncat <<-B\ny\nB"
    assert guard.strip_heredocs(two) == "cat <<A\necho mid\ncat <<-B\n"
