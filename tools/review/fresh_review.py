#!/usr/bin/env python3
"""fresh-review — independent, fresh-context review of the branch diff, with a receipt (plan step 3.3).

  bin/fresh-review [--base origin/main] [--model opus] [--target claude] [--dry-run]
`git diff <base>...HEAD` goes through the egress screen, then with the version-controlled
prompt (tools/review/prompt.md) to `claude -p` with no tools and a JSON schema. The verdict
lands in .git/fresh-review/<head-sha>.json and on stdout. Advisory, never a hook: exit 0 for
APPROVE or COMMENT, 1 for BLOCKER, 3 when the screen holds the diff, 2 on errors.
At work the same prompt is .github/instructions/review.instructions.md for Copilot code review.
"""
import argparse
import datetime as _dt
import hashlib
import json
import os
import subprocess
import sys
from typing import Optional

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "egress"))
import egress_screen  # noqa: E402

PROMPT_PATH = os.path.join(HERE, "prompt.md")
SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["APPROVE", "COMMENT", "BLOCKER"]},
        "summary": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "severity": {"type": "string", "enum": ["BLOCKER", "MAJOR", "MINOR"]},
                    "file": {"type": "string"},
                    "line": {"type": "integer"},
                    "summary": {"type": "string"},
                },
                "required": ["severity", "file", "line", "summary"],
            },
        },
    },
    "required": ["verdict", "summary", "findings"],
}
EXIT_BY_VERDICT = {"APPROVE": 0, "COMMENT": 0, "BLOCKER": 1}


class ReviewError(Exception):
    pass


def git(args: list, cwd: str) -> str:
    r = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        raise ReviewError(f"git {' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def default_base(cwd: str) -> str:
    for cand in ("origin/main", "main"):
        if subprocess.run(["git", "rev-parse", "--verify", "-q", cand], cwd=cwd, capture_output=True).returncode == 0:
            return cand
    raise ReviewError("no origin/main or main to diff against; pass --base")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def call_claude(prompt: str, model: str, claude_bin: str = "claude") -> dict:
    cmd = [claude_bin, "-p", "--model", model, "--output-format", "json", "--tools", "", "--no-session-persistence",
           "--json-schema", json.dumps(SCHEMA)]
    try:
        r = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=900)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ReviewError(f"{claude_bin}: {exc}") from exc
    if r.returncode != 0:
        raise ReviewError(f"{claude_bin} exited {r.returncode}: {r.stderr.strip()[:400]}")
    try:
        data = json.loads(r.stdout)
    except ValueError as exc:
        raise ReviewError(f"{claude_bin} returned no JSON: {r.stdout[:200]!r}") from exc
    if data.get("is_error") or "structured_output" not in data:
        raise ReviewError(f"{claude_bin} gave no structured verdict: {str(data.get('result'))[:300]}")
    return data


def main(argv: list, cwd: Optional[str] = None, out=None) -> int:
    out = out or sys.stdout
    cwd = cwd or os.getcwd()
    ap = argparse.ArgumentParser(prog="fresh-review", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base")
    ap.add_argument("--model", default="opus")
    ap.add_argument("--target", default="claude", help="egress target name (claude at home)")
    ap.add_argument("--dry-run", action="store_true", help="screen and size the prompt, do not call the model")
    ap.add_argument("--claude-bin", default="claude")
    ns = ap.parse_args(argv)
    try:
        base = ns.base or default_base(cwd)
        head = git(["rev-parse", "HEAD"], cwd).strip()
        base_sha = git(["rev-parse", base], cwd).strip()
        diff = git(["diff", f"{base}...HEAD"], cwd)
        if not diff.strip():
            out.write(f"fresh-review: nothing to review ({base}...HEAD is empty)\n")
            return 0
        held = egress_screen.screen_text(diff, ns.target, egress_screen.load_config(cwd))
        if held:
            out.write("fresh-review: diff held by the egress screen: " + ", ".join(held) + "\n")
            return 3
        with open(PROMPT_PATH, encoding="utf-8") as fh:
            prompt_text = fh.read()
        header = f"Diff ({base}...HEAD, {len(diff.splitlines())} lines):"
        prompt = prompt_text.rstrip() + f"\n\n{header}\n\n```diff\n{diff}\n```\n"
        if ns.dry_run:
            out.write(f"fresh-review: dry run, prompt {len(prompt)} chars, diff {len(diff)} chars, base {base}\n")
            return 0
        started = _dt.datetime.now(_dt.timezone.utc)
        data = call_claude(prompt, ns.model, ns.claude_bin)
        verdict = data["structured_output"]
        usage = data.get("modelUsage") or {}
        receipt = {
            "sha": head, "base": base, "base_sha": base_sha, "ts": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "model_requested": ns.model, "models": sorted(usage), "cost_usd": data.get("total_cost_usd"),
            "duration_ms": data.get("duration_ms"), "prompt_sha256": sha256(prompt), "diff_sha256": sha256(diff),
            "prompt_file": os.path.relpath(PROMPT_PATH, cwd), "verdict": verdict["verdict"],
            "summary": verdict.get("summary", ""), "findings": verdict.get("findings", []),
        }
        rdir = os.path.join(git(["rev-parse", "--git-dir"], cwd).strip(), "fresh-review")
        rdir = rdir if os.path.isabs(rdir) else os.path.join(cwd, rdir)
        os.makedirs(rdir, exist_ok=True)
        rpath = os.path.join(rdir, f"{head}.json")
        with open(rpath, "w", encoding="utf-8") as fh:
            json.dump(receipt, fh, indent=2, sort_keys=True)
            fh.write("\n")
    except ReviewError as exc:
        out.write(f"fresh-review: error: {exc}\n")
        return 2
    cost = f"${receipt['cost_usd']:.2f}" if isinstance(receipt["cost_usd"], (int, float)) else "cost n/a"
    out.write(f"fresh-review: {receipt['verdict']} ({len(receipt['findings'])} findings) "
              f"model {', '.join(receipt['models']) or ns.model}, {cost}; receipt {os.path.relpath(rpath, cwd)}\n")
    if receipt["summary"]:
        out.write(f"  {receipt['summary']}\n")
    for f in receipt["findings"]:
        out.write(f"  {f['severity']:<7} {f['file']}:{f['line']}  {f['summary']}\n")
    return EXIT_BY_VERDICT.get(receipt["verdict"], 2)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
