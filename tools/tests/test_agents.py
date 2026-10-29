"""Agent frontmatter contract (plan step 1.6): every agent pins a model tier; advisory agents stay read-only."""
import pathlib
import re

import pytest

AGENTS = sorted((pathlib.Path(__file__).resolve().parents[2] / "agents").glob("*.md"))
TIERS = {"opus", "fable", "sonnet", "haiku"}
WRITE_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
ADVISORY = ("reviewer", "planner", "advisor")


def frontmatter(path: pathlib.Path) -> dict:
    m = re.match(r"---\n(.*?)\n---\n", path.read_text(), re.DOTALL)
    assert m, f"{path.name}: no frontmatter"
    fm = {}
    for line in m.group(1).splitlines():
        key, _, value = line.partition(":")
        fm[key.strip()] = value.strip()
    return fm


def test_agents_found():
    assert AGENTS, "agents/*.md not found: the test is looking in the wrong place"


@pytest.mark.parametrize("path", AGENTS, ids=lambda p: p.stem)
def test_model_pinned(path):
    assert frontmatter(path).get("model") in TIERS, f"{path.name}: model must be one of {sorted(TIERS)}"


@pytest.mark.parametrize("path", AGENTS, ids=lambda p: p.stem)
def test_advisory_agents_cannot_write(path):
    if not any(word in path.stem for word in ADVISORY):
        pytest.skip("not an advisory agent")
    tools = {t.strip() for t in frontmatter(path).get("tools", "").split(",") if t.strip()}
    assert not (tools & WRITE_TOOLS), f"{path.name}: advisory agent lists write tools {sorted(tools & WRITE_TOOLS)}"
