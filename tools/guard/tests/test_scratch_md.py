"""scratch-md needs a real tree: 'new file' and 'inside a git repo' are filesystem facts."""
import subprocess


def _repo(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    return str(tmp_path)


def _write(guard, cwd, path, tool="Write"):
    raw = {"hook_event_name": "PreToolUse", "tool_name": tool, "cwd": cwd,
           "tool_input": {"file_path": path, "content": "x"}}
    return guard.Event(raw)


def test_new_md_at_repo_root_asks(guard, tmp_path):
    cwd = _repo(tmp_path)
    got = guard.rule_scratch_md(_write(guard, cwd, "FINDINGS.md"), guard.DEFAULTS)
    assert got and got[0] == "ask" and "FINDINGS.md" in got[1]
    got = guard.rule_scratch_md(_write(guard, cwd, "src/NOTES.markdown"), guard.DEFAULTS)
    assert got and got[0] == "ask"


def test_documented_homes_pass(guard, tmp_path):
    cwd = _repo(tmp_path)
    for p in ("docs/x.md", "README.md", ".claude/notes.md", "pkg/README.md", "skills/x/SKILL.md", "DECISIONS.md",
              ".github/PULL_REQUEST_TEMPLATE.md", "evidence/v1/summary.md"):
        assert guard.rule_scratch_md(_write(guard, cwd, p), guard.DEFAULTS) is None, p


def test_existing_file_and_non_markdown_not_judged(guard, tmp_path):
    cwd = _repo(tmp_path)
    (tmp_path / "NOTES.md").write_text("x")
    assert guard.rule_scratch_md(_write(guard, cwd, "NOTES.md"), guard.DEFAULTS) is None
    assert guard.rule_scratch_md(_write(guard, cwd, "notes.txt"), guard.DEFAULTS) is None


def test_outside_a_git_tree_not_judged(guard, tmp_path):
    assert guard.rule_scratch_md(_write(guard, str(tmp_path), "NOTES.md"), guard.DEFAULTS) is None


def test_edit_tool_not_judged(guard, tmp_path):
    cwd = _repo(tmp_path)
    assert guard.rule_scratch_md(_write(guard, cwd, "NOTES.md", tool="Edit"), guard.DEFAULTS) is None


def test_modes(guard, tmp_path, monkeypatch):
    cwd = _repo(tmp_path)
    ev = _write(guard, cwd, "SUMMARY.md")
    assert guard.rule_scratch_md(ev, {**guard.DEFAULTS, "scratch_md_mode": "deny"})[0] == "deny"
    assert guard.rule_scratch_md(ev, {**guard.DEFAULTS, "scratch_md_mode": "off"}) is None
    monkeypatch.setenv("KZ_SCRATCH_MD", "deny")
    assert guard.load_config(cwd)["scratch_md_mode"] == "deny"


def test_copilot_create_shape(guard, tmp_path):
    cwd = _repo(tmp_path)
    raw = {"hook_event_name": "PreToolUse", "tool_name": "create", "cwd": cwd, "timestamp": "x",
           "tool_input": {"path": "SUMMARY.md", "file_text": "x"}}
    got = guard.rule_scratch_md(guard.Event(raw), guard.DEFAULTS)
    assert got and got[0] == "ask"
