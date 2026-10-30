#!/usr/bin/env python3
"""latest-tag — flag floating image references: `:latest`, or no tag at all (plan step 3.7).

AGENTS.md: image tags are the git SHA, never `latest`. A reference without a tag is `latest` by
definition, so it counts too; a digest (`@sha256:...`) always passes; `${VAR}` references are the
variable owner's problem, not this scanner's. Files are judged by name: Dockerfiles (Dockerfile,
Dockerfile.*, *.Dockerfile, *.dockerfile, Containerfile), compose files (compose*.yml|yaml,
docker-compose*.yml|yaml) and GitHub workflows (.github/workflows/*.yml|yaml). Build-stage names
(`FROM base`) and `scratch` pass.

  latest_tag.py hook            PostToolUse: scan the file just written; findings come back as hook
                                feedback (Claude Code: `decision: block` + `reason`; Copilot:
                                `additionalContext`); exit 0 always
  latest_tag.py scan [PATH...]  CI: scan PATHs (a file is read whatever its name: .yml/.yaml as
                                compose/workflow, anything else as a Dockerfile; a directory by name),
                                default every tracked file of the repo. One line per finding on stdout,
                                a summary on stderr; exit 1 when any finding, 2 when nothing could be scanned
"""
import json
import os
import re
import subprocess
import sys

VERSION = "0.1.0"
_DOCKERFILE_RE = re.compile(r"^(Dockerfile(\..+)?|.+\.[Dd]ockerfile|Containerfile(\..+)?)$")
_COMPOSE_RE = re.compile(r"^(docker-)?compose[^/]*\.ya?ml$")
_WORKFLOW_RE = re.compile(r"(^|/)\.github/workflows/[^/]+\.ya?ml$")
_FROM_RE = re.compile(r"^\s*FROM\s+(.+?)\s*$", re.IGNORECASE)
_IMAGE_RE = re.compile(r"^\s*-?\s*image\s*:\s*(.+?)\s*$")
_USES_DOCKER_RE = re.compile(r"^\s*-?\s*uses\s*:\s*[\"']?docker://(.+?)[\"']?\s*$")
WHY = "image tags are the git SHA, never latest (AGENTS.md, security reflexes)"
HOW = "pin a tag (and a digest where the registry is not yours); a stage name or scratch is fine in FROM"


def kind_of(path: str):
    """'dockerfile' | 'yaml' | None, by file name."""
    norm = path.replace("\\", "/")
    base = norm.rsplit("/", 1)[-1]
    if _DOCKERFILE_RE.match(base):
        return "dockerfile"
    if _COMPOSE_RE.match(base) or _WORKFLOW_RE.search(norm):
        return "yaml"
    return None


def tag_of(ref: str) -> str:
    """'digest' | 'latest' | 'none' | 'tag' for an image reference."""
    name, _, digest = ref.partition("@")
    if digest:
        return "digest"
    colon = name.rfind(":")
    if colon > name.rfind("/"):
        return "latest" if name[colon + 1:] == "latest" else "tag"
    return "none"


def _floating(ref: str):
    """Reason text when the reference floats, None when it is pinned or cannot be judged."""
    if not ref or "$" in ref or "{{" in ref:
        return None
    kind = tag_of(ref)
    if kind == "latest":
        return ":latest tag"
    if kind == "none":
        return "no tag (floats to :latest)"
    return None


def _yaml_value(raw: str) -> str:
    text = raw.strip()
    if text.startswith(("'", '"')) and len(text) >= 2 and text[-1] == text[0]:
        return text[1:-1].strip()
    return re.split(r"\s+#", text, maxsplit=1)[0].strip()


def scan_text(text: str, kind: str) -> list:
    """[(line_no, reason, line_text)] for a Dockerfile or a compose/workflow file."""
    out = []
    stages = set()
    for n, line in enumerate(text.splitlines(), 1):
        ref = None
        if kind == "dockerfile":
            m = _FROM_RE.match(line)
            if not m:
                continue
            tokens = [t for t in m.group(1).split() if not t.startswith("--")]
            if not tokens:
                continue
            ref = tokens[0]
            if len(tokens) >= 3 and tokens[1].lower() == "as":
                stages.add(tokens[2].lower())
            if ref.lower() == "scratch" or ref.lower() in stages:
                continue
        else:
            m = _IMAGE_RE.match(line)
            if m:
                ref = _yaml_value(m.group(1))
            else:
                m = _USES_DOCKER_RE.match(line)
                if not m:
                    continue
                ref = m.group(1).strip()
        reason = _floating(ref)
        if reason:
            out.append((n, reason, line.strip()))
    return out


def scan_file(path: str, kind: str) -> list:
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            text = fh.read()
    except OSError:
        return []
    return [(path, n, reason, line) for n, reason, line in scan_text(text, kind)]


def tracked_files(root: str) -> list:
    try:
        r = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    return [p for p in r.stdout.split("\0") if p]


def candidates(paths: list, root: str) -> list:
    """[(path, kind)] to scan: named files by extension, directories and the git tree by file name."""
    out = []
    if not paths:
        return [(p, k) for p in tracked_files(root) for k in [kind_of(p)] if k]
    for p in paths:
        if os.path.isdir(p):
            for dirpath, dirnames, filenames in os.walk(p):
                dirnames[:] = [d for d in dirnames if d not in (".git", "node_modules")]
                for f in sorted(filenames):
                    full = os.path.join(dirpath, f)
                    k = kind_of(full)
                    if k:
                        out.append((full, k))
        elif os.path.isfile(p):
            out.append((p, "yaml" if p.lower().endswith((".yml", ".yaml")) else "dockerfile"))
    return out


def cmd_scan(paths: list, out, err, root: str = ".") -> int:
    files = candidates(paths, root)
    if not files and not paths:
        err.write("latest-tag: nothing to scan (not a git repository? name the paths)\n")
        return 2
    findings = []
    for path, kind in files:
        findings += scan_file(path, kind)
    for path, n, reason, line in findings:
        out.write(f"{path}:{n}: {reason}: {line}\n")
    err.write(f"latest-tag: {len(findings)} finding(s) in {len(files)} file(s) scanned\n")
    return 1 if findings else 0


def is_copilot(raw: dict) -> bool:
    """Same tell the guard uses: Copilot payloads carry `timestamp` or camelCase keys."""
    return "timestamp" in raw or "toolName" in raw or "toolArgs" in raw


def feedback(findings: list, copilot: bool) -> dict:
    lines = [f"  {os.path.basename(path)}:{n}: {reason}: {line}" for path, n, reason, line in findings[:20]]
    msg = f"latest-tag: {WHY}:\n" + "\n".join(lines) + f"\n  How: {HOW}"
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
    args = raw.get("tool_input") if "tool_input" in raw else raw.get("toolArgs")
    args = args if isinstance(args, dict) else {}
    path = next((args[k] for k in ("file_path", "path", "filePath") if isinstance(args.get(k), str)), "")
    kind = kind_of(path) if path else None
    if not kind:
        return 0
    findings = scan_file(os.path.expanduser(path), kind)
    if findings:
        out.write(json.dumps(feedback(findings, is_copilot(raw))) + "\n")
    return 0


def main(argv: list, stdin=None, out=None, err=None) -> int:
    stdin, out, err = stdin or sys.stdin, out or sys.stdout, err or sys.stderr
    if argv[:1] == ["hook"]:
        return hook(stdin, out)
    if argv[:1] == ["scan"]:
        return cmd_scan(argv[1:], out, err)
    out.write(__doc__.strip() + "\n")
    return 0 if argv[:1] in (["help"], ["-h"], ["--help"]) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
