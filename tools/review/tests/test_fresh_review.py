"""fresh-review against a fake `claude` binary: screening first, receipt always, verdict drives the exit code."""
import io
import json
import os
import pathlib
import stat
import subprocess

ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t",
       "PATH": os.environ.get("PATH", "")}


def repo_with_branch(tmp_path, change="assert x == 1  # touched\n"):
    r = tmp_path / "repo"
    r.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main", str(r)], check=True)
    (r / "test_x.py").write_text("def test_x():\n    x = 1\n    assert x == 1\n")
    subprocess.run(["git", "-C", str(r), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(r), "commit", "-q", "-m", "feat: start"], check=True, env=ENV)
    subprocess.run(["git", "-C", str(r), "switch", "-q", "-c", "step-x"], check=True)
    (r / "test_x.py").write_text("def test_x():\n    x = 1\n    " + change)
    subprocess.run(["git", "-C", str(r), "commit", "-q", "-am", "fix: weaken"], check=True, env=ENV)
    return r


def fake_claude(tmp_path, verdict):
    d = tmp_path / "bin"
    d.mkdir(exist_ok=True)
    marker = tmp_path / "called"
    payload = {"type": "result", "is_error": False, "total_cost_usd": 0.42, "duration_ms": 1234,
               "modelUsage": {"claude-opus-4-1": {"inputTokens": 10}}, "result": "x", "structured_output": verdict}
    script = d / "claude"
    script.write_text(f"#!/bin/sh\ncat > /dev/null\ntouch '{marker}'\ncat <<'EOF'\n{json.dumps(payload)}\nEOF\n")
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return str(script), marker


def test_blocker_writes_receipt_and_exits_1(review, tmp_path):
    r = repo_with_branch(tmp_path, change="assert True\n")
    finding = {"severity": "BLOCKER", "file": "test_x.py", "line": 3, "summary": "assert True replaces assert x == 1"}
    verdict = {"verdict": "BLOCKER", "summary": "assertion weakened", "findings": [finding]}
    claude, marker = fake_claude(tmp_path, verdict)
    out = io.StringIO()
    code = review.main(["--base", "main", "--claude-bin", claude], cwd=str(r), out=out)
    assert code == 1 and marker.exists()
    text = out.getvalue()
    assert "BLOCKER (1 findings)" in text and "test_x.py:3" in text and "$0.42" in text
    head = subprocess.run(["git", "-C", str(r), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    receipt = json.loads((r / ".git" / "fresh-review" / f"{head}.json").read_text())
    assert receipt["verdict"] == "BLOCKER" and receipt["sha"] == head and receipt["base"] == "main"
    assert receipt["models"] == ["claude-opus-4-1"] and len(receipt["diff_sha256"]) == 64
    assert receipt["prompt_file"].endswith("tools/review/prompt.md")


def test_approve_exits_0(review, tmp_path):
    r = repo_with_branch(tmp_path)
    claude, _ = fake_claude(tmp_path, {"verdict": "APPROVE", "summary": "", "findings": []})
    out = io.StringIO()
    assert review.main(["--base", "main", "--claude-bin", claude], cwd=str(r), out=out) == 0
    assert out.getvalue().startswith("fresh-review: APPROVE (0 findings)")


def test_planted_secret_is_held_before_any_call(review, tmp_path):
    r = repo_with_branch(tmp_path, change="token = 'ghp_" + "A1" * 18 + "'\n")
    claude, marker = fake_claude(tmp_path, {"verdict": "APPROVE", "summary": "", "findings": []})
    out = io.StringIO()
    code = review.main(["--base", "main", "--claude-bin", claude], cwd=str(r), out=out)
    assert code == 3 and "held by the egress screen" in out.getvalue() and "secret:github-token" in out.getvalue()
    assert not marker.exists(), "the model was never called"


def test_dry_run_and_empty_diff(review, tmp_path):
    r = repo_with_branch(tmp_path)
    out = io.StringIO()
    assert review.main(["--base", "main", "--dry-run"], cwd=str(r), out=out) == 0 and "dry run" in out.getvalue()
    out = io.StringIO()
    assert review.main(["--base", "HEAD", "--claude-bin", "/nonexistent"], cwd=str(r), out=out) == 0
    assert "nothing to review" in out.getvalue()


def test_model_failure_is_exit_2(review, tmp_path):
    r = repo_with_branch(tmp_path)
    out = io.StringIO()
    assert review.main(["--base", "main", "--claude-bin", "/nonexistent/claude"], cwd=str(r), out=out) == 2
    assert out.getvalue().startswith("fresh-review: error:")


def test_work_instructions_carry_the_same_prompt(review):
    root = pathlib.Path(review.HERE).parents[1]
    prompt = (root / "tools" / "review" / "prompt.md").read_text().strip()
    instr = (root / ".github" / "instructions" / "review.instructions.md").read_text()
    body = instr.split("---", 2)[2].strip()
    assert body == prompt, "review.instructions.md must stay a copy of prompt.md (plus the applyTo frontmatter)"
    assert instr.startswith("---\napplyTo:")


def test_rerun_never_overwrites_a_receipt(review, tmp_path):
    r = repo_with_branch(tmp_path)
    blocker = {"verdict": "BLOCKER", "summary": "s", "findings": []}
    claude, _ = fake_claude(tmp_path, blocker)
    assert review.main(["--base", "main", "--claude-bin", claude], cwd=str(r), out=io.StringIO()) == 1
    claude, _ = fake_claude(tmp_path, {"verdict": "APPROVE", "summary": "", "findings": []})
    assert review.main(["--base", "main", "--claude-bin", claude], cwd=str(r), out=io.StringIO()) == 0
    receipts = sorted(p.name for p in (r / ".git" / "fresh-review").iterdir())
    head = subprocess.run(["git", "-C", str(r), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    assert receipts == [f"{head}.2.json", f"{head}.json"]
    assert json.loads((r / ".git" / "fresh-review" / f"{head}.json").read_text())["verdict"] == "BLOCKER"


def test_malformed_model_answer_is_exit_2(review, tmp_path):
    r = repo_with_branch(tmp_path)
    for bad in (None, {"verdict": "MAYBE", "findings": []}, {"verdict": "APPROVE", "findings": "none"}):
        claude, _ = fake_claude(tmp_path, bad)
        out = io.StringIO()
        assert review.main(["--base", "main", "--claude-bin", claude], cwd=str(r), out=out) == 2, bad
        assert "no usable structured verdict" in out.getvalue()

