import importlib.util
import os
import pathlib
import subprocess
import types

import pytest


@pytest.fixture(scope="session")
def memstore():
    src = pathlib.Path(__file__).resolve().parents[1] / "memstore.py"
    spec = importlib.util.spec_from_file_location("memstore", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GOOD = """---
name: {name}
description: {desc}
metadata:
  type: {typ}
  stale_after: 2099-01-01
---

Body of {name}.
"""


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A fake ~/.claude/projects with two project slugs, each holding memory files; HOME points at it."""
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("GIT_AUTHOR_NAME", "t")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "t@example.invalid")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "t")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "t@example.invalid")
    monkeypatch.delenv("KZ_MEMORY_PUSH", raising=False)
    monkeypatch.delenv("KZ_MEMORY_STORE", raising=False)
    monkeypatch.delenv("KZ_MEMORY_WORKTREE", raising=False)
    projects = tmp_path / ".claude" / "projects"
    for slug, names in {"-Users-t-Developer-alpha": ["a-one", "a-two"], "-Users-t-Developer-beta": ["b-one"]}.items():
        d = projects / slug / "memory"
        d.mkdir(parents=True)
        for n in names:
            (d / f"{n}.md").write_text(GOOD.format(name=n, desc=f"about {n}", typ="project"), encoding="utf-8")
        (d / "MEMORY.md").write_text("# Memory index\n", encoding="utf-8")
        # noise that must stay out of the store
        (projects / slug / "session.jsonl").write_text("{}\n", encoding="utf-8")
        (projects / slug / "tool-results").mkdir()
        (projects / slug / "tool-results" / "x.txt").write_text("big\n", encoding="utf-8")
    return tmp_path


def tracked(store: str, worktree: str) -> list:
    env = {**os.environ, "GIT_DIR": store, "GIT_WORK_TREE": worktree}
    r = subprocess.run(["git", "ls-files"], env=env, capture_output=True, text=True, cwd=worktree)
    return sorted(r.stdout.split())


@pytest.fixture(scope="session")
def helpers():
    """Shared template and git helper; a fixture rather than `from conftest import` (several conftests exist)."""
    return types.SimpleNamespace(GOOD=GOOD, tracked=tracked)
