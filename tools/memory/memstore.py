#!/usr/bin/env python3
"""memstore — Claude Code memory files under git, with a schema (plan steps 3.4, 3.5).

A bare repository (default ~/.claude/memory-store.git) whose work tree is ~/.claude/projects;
info/exclude keeps only */memory/** in it. Every memory write becomes one commit through the
PostToolUse hook; push is OFF unless KZ_MEMORY_PUSH names the project slugs (or `*`).

  memstore.py init                      create the store and import what exists
  memstore.py hook                      PostToolUse: commit the written memory file, validate it (exit 2 = feedback)
  memstore.py commit <path>             commit one memory path (used by the hook)
  memstore.py push                      push when KZ_MEMORY_PUSH allows it and a remote exists
  memstore.py digest [--cwd DIR]        <= 8 lines for the session start
  memstore.py log [-n N]
  memstore.py validate <file>...        schema warnings; exit 2 when any
  memstore.py index [--cwd DIR] [--write]   regenerate MEMORY.md from frontmatter (<= 18 KB)
  memstore.py triage [--cwd DIR]        stale, unverified, deprecated, superseded at a glance
  memstore.py deprecate <file> [--by SLUG]  mark deprecated (or superseded by SLUG) and commit
Options: --store DIR, --worktree DIR (env KZ_MEMORY_STORE, KZ_MEMORY_WORKTREE).
"""
import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys
import time
from typing import Optional

EXCLUDE = "*\n!*/\n!*/memory/\n!*/memory/**\n"
TYPES = ("user", "feedback", "project", "reference")
STATUSES = ("active", "deprecated", "superseded")
NEEDS_STALE_AFTER = ("project", "reference")
INDEX_MAX_BYTES = 18_000
DIGEST_MAX_LINES = 8
DIGEST_MAX_BYTES = 600
_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Store:
    def __init__(self, store: Optional[str] = None, worktree: Optional[str] = None):
        self.store = os.path.expanduser(store or os.environ.get("KZ_MEMORY_STORE") or "~/.claude/memory-store.git")
        self.worktree = os.path.expanduser(worktree or os.environ.get("KZ_MEMORY_WORKTREE") or "~/.claude/projects")

    def git(self, args: list, check: bool = True) -> subprocess.CompletedProcess:
        env = {**os.environ, "GIT_DIR": self.store, "GIT_WORK_TREE": self.worktree}
        r = subprocess.run(["git", *args], env=env, capture_output=True, text=True, cwd=self.worktree)
        if check and r.returncode != 0:
            raise RuntimeError(f"git {' '.join(args[:2])}: {r.stderr.strip()[:300]}")
        return r

    def exists(self) -> bool:
        return os.path.isdir(self.store)

    def init(self, out) -> int:
        os.makedirs(self.worktree, exist_ok=True)
        if not self.exists():
            subprocess.run(["git", "init", "-q", "--bare", "-b", "main", self.store], check=True)
            out.write(f"created {self.store} (work tree {self.worktree})\n")
        with open(os.path.join(self.store, "info", "exclude"), "w", encoding="utf-8") as fh:
            fh.write(EXCLUDE)
        self.git(["config", "status.showUntrackedFiles", "all"])
        self.git(["add", "-A"])
        if self.git(["diff", "--cached", "--quiet"], check=False).returncode != 0:
            self.git(["commit", "-q", "-m", "memory: import existing files"])
            stat = self.git(["show", "--stat", "--format=", "HEAD"]).stdout.strip().splitlines()[-1]
            out.write("imported: " + stat + "\n")
        else:
            out.write("nothing new to import\n")
        out.write(f"tracked files: {len(self.git(['ls-files']).stdout.split())}\n")
        return 0

    def memory_rel(self, path: str) -> Optional[str]:
        """'<slug>/memory/<file>' when the path is a memory file under the work tree, else None."""
        p = os.path.abspath(os.path.expanduser(path))
        try:
            rel = os.path.relpath(p, self.worktree)
        except ValueError:
            return None
        parts = rel.split(os.sep)
        if rel.startswith("..") or len(parts) < 3 or parts[1] != "memory":
            return None
        return "/".join(parts)

    def commit(self, path: str, out) -> int:
        rel = self.memory_rel(path)
        if rel is None:
            return 0
        if not self.exists():
            out.write("memstore: no store yet; run `memstore.py init`\n")
            return 0
        slug = rel.split("/")[0]
        self.git(["add", "-A", "--", f"{slug}/memory"])
        status = self.git(["diff", "--cached", "--name-status", "--", f"{slug}/memory"]).stdout.strip()
        if not status:
            return 0
        verbs = {"A": "add", "M": "update", "D": "delete", "R": "rename"}
        first = status.splitlines()[0].split("\t")
        action = verbs.get(first[0][:1], "change")
        name = os.path.splitext(os.path.basename(first[-1]))[0]
        n = len(status.splitlines())
        msg = f"memory({slug}): {action} {name}" + (f" (+{n - 1} more)" if n > 1 else "")
        for attempt in range(3):  # parallel Write/Edit hooks race for index.lock
            r = self.git(["commit", "-q", "-m", msg], check=False)
            if r.returncode == 0:
                break
            if "index.lock" not in r.stderr or attempt == 2:
                raise RuntimeError(f"git commit: {r.stderr.strip()[:300]}")
            time.sleep(0.2 * (attempt + 1))
        out.write(f"memstore: committed {msg}\n")
        return 0

    def push(self, out) -> int:
        if not self.exists():
            out.write("memstore: no store\n")
            return 1
        if self.git(["remote", "get-url", "origin"], check=False).returncode != 0:
            out.write("memstore: no remote `origin`; push off (add a private remote first)\n")
            return 0
        allow = {s.strip() for s in os.environ.get("KZ_MEMORY_PUSH", "").split(",") if s.strip()}
        if not allow:
            out.write("memstore: push off (set KZ_MEMORY_PUSH=<slug,...> or * to allow)\n")
            return 0
        if "*" not in allow:
            has_remote_main = self.git(["rev-parse", "--verify", "-q", "origin/main"], check=False).returncode == 0
            rng = "origin/main..HEAD" if has_remote_main else "HEAD"  # first push: every commit counts
            r = self.git(["log", "--name-only", "--format=", rng], check=False)
            if r.returncode != 0:  # fail closed: an unknown set of touched projects must not reach GitHub
                out.write("memstore: push refused, cannot list unpushed commits: " + r.stderr.strip()[:200] + "\n")
                return 3
            touched = {ln.split("/")[0] for ln in r.stdout.split() if "/" in ln}
            blocked = sorted(touched - allow)
            if blocked:
                out.write("memstore: push refused, unpushed commits touch projects outside KZ_MEMORY_PUSH: "
                          + ", ".join(blocked) + "\n")
                return 3
        self.git(["push", "-q", "-u", "origin", "main"])
        out.write("memstore: pushed\n")
        return 0

    def log(self, n: int, out) -> int:
        if not self.exists():
            out.write("memstore: no store\n")
            return 1
        out.write(self.git(["log", "--oneline", f"-n{n}"], check=False).stdout)
        return 0


# ----------------------------------------------------------------------------
# Schema (step 3.5): name, description, metadata.type + status, stale_after, verified/verified_on, superseded_by
# ----------------------------------------------------------------------------


def parse_frontmatter(text: str) -> dict:
    """Flat keys plus a `metadata` dict; the minimal YAML subset these files use."""
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    data: dict = {"metadata": {}}
    section = None
    for line in text[4:end].splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if line.startswith(" ") and section:
            key, _, value = line.strip().partition(":")
            data[section][key.strip()] = _scalar(value)
        else:
            key, _, value = line.partition(":")
            key = key.strip()
            if value.strip() == "" and key:
                data[key] = {}
                section = key
            else:
                data[key] = _scalar(value)
                section = None
    return data


def _scalar(value: str):
    v = value.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        v = v[1:-1]
    if v.lower() in ("true", "yes"):
        return True
    if v.lower() in ("false", "no"):
        return False
    return v


def validate_text(text: str, today: Optional[_dt.date] = None) -> list:
    today = today or _dt.date.today()
    fm = parse_frontmatter(text)
    if not fm:
        return ["no frontmatter (--- name/description/metadata ---)"]
    meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
    out = []
    if not fm.get("name"):
        out.append("missing `name`")
    if not fm.get("description"):
        out.append("missing `description`")
    typ = meta.get("type")
    if typ not in TYPES:
        out.append(f"metadata.type must be one of {', '.join(TYPES)} (got {typ!r})")
    status = meta.get("status", "active")
    if status not in STATUSES:
        out.append(f"metadata.status must be one of {', '.join(STATUSES)} (got {status!r})")
    if status == "superseded" and not meta.get("superseded_by"):
        out.append("status superseded needs metadata.superseded_by: <slug>")
    if meta.get("superseded_by") and status == "active":
        out.append("has superseded_by but status is active")
    stale = meta.get("stale_after")
    if typ in NEEDS_STALE_AFTER and not stale:
        out.append(f"metadata.stale_after: YYYY-MM-DD is required for type {typ} (facts about work and links age)")
    if stale:
        stale_date = _parse_date(stale)
        if stale_date is None:
            out.append(f"metadata.stale_after is not a date: {stale!r}")
        elif stale_date < today and status == "active":
            out.append(f"stale since {stale}: re-verify, then move stale_after (and set verified_on), or deprecate")
    if meta.get("verified") is True and _parse_date(meta.get("verified_on", "")) is None:
        out.append("verified: true needs metadata.verified_on: YYYY-MM-DD")
    return out


def _parse_date(value) -> Optional[_dt.date]:
    if not _DATE_RE.match(str(value)):
        return None
    try:
        return _dt.date.fromisoformat(str(value))
    except ValueError:  # 2026-02-30 passes the regex
        return None


def read_text(path: str) -> str:
    """Memory files are text; a stray byte must not take the hook or the session start down."""
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def validate_file(path: str, today: Optional[_dt.date] = None) -> list:
    try:
        return validate_text(read_text(path), today)
    except OSError as exc:
        return [f"unreadable: {exc}"]


def cwd_slug(cwd: str) -> str:
    """Claude Code's project directory name for a cwd: every character outside [A-Za-z0-9] becomes a dash
    (checked 2026-10-29 against ~/.claude/projects: `/`, `.`, `_` and spaces all map to `-`)."""
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(cwd))


def memory_files(worktree: str, slug: str) -> list:
    d = os.path.join(worktree, slug, "memory")
    if not os.path.isdir(d):
        return []
    return sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".md") and f != "MEMORY.md")


def build_index(worktree: str, slug: str) -> str:
    rows = []
    for path in memory_files(worktree, slug):
        try:
            fm = parse_frontmatter(read_text(path))
        except OSError:
            continue
        meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
        if meta.get("status", "active") != "active":
            continue
        name = fm.get("name") or os.path.splitext(os.path.basename(path))[0]
        rows.append((meta.get("type", "zz"), str(name), str(fm.get("description", "")), os.path.basename(path)))
    rows.sort()
    lines = ["# Memory index", ""]
    size = sum(len(ln.encode()) + 1 for ln in lines)
    kept = 0
    for _typ, name, desc, fname in rows:
        line = f"- [{name}]({fname}) — {desc}"
        if size + len(line.encode()) + 1 > INDEX_MAX_BYTES - 120:
            lines.append(f"- … {len(rows) - kept} more not indexed (size cap); run `memstore.py triage` and deprecate")
            break
        lines.append(line)
        size += len(line.encode()) + 1
        kept += 1
    return "\n".join(lines) + "\n"


def triage_rows(worktree: str, slug: str, today: Optional[_dt.date] = None) -> list:
    rows = []
    for path in memory_files(worktree, slug):
        try:
            text = read_text(path)
        except OSError as exc:
            text = ""
            exc_note = f"unreadable: {exc}"
        else:
            exc_note = ""
        fm = parse_frontmatter(text)
        meta = fm.get("metadata") if isinstance(fm.get("metadata"), dict) else {}
        warnings = [exc_note] if exc_note else validate_text(text, today)
        rows.append({
            "file": os.path.basename(path), "type": meta.get("type", "?"), "status": meta.get("status", "active"),
            "stale_after": meta.get("stale_after", ""), "verified_on": meta.get("verified_on", ""),
            "warnings": warnings,
        })
    return rows


def set_metadata(path: str, **fields) -> None:
    """Insert or replace keys inside the `metadata:` block of a memory file's frontmatter."""
    text = read_text(path)
    end = text.find("\n---", 4) if text.startswith("---\n") else -1
    if end < 0:
        raise RuntimeError(f"{path}: no frontmatter")
    head, tail = text[4:end], text[end:]
    lines = head.splitlines()
    try:
        mi = next(i for i, ln in enumerate(lines) if ln.strip() == "metadata:")
    except StopIteration:
        lines.append("metadata:")
        mi = len(lines) - 1
    block_end = mi + 1
    while block_end < len(lines) and lines[block_end].startswith(" "):
        block_end += 1
    block = lines[mi + 1 : block_end]
    for k, v in fields.items():
        rendered = f"  {k}: {v}"
        for j, ln in enumerate(block):
            if ln.strip().startswith(k + ":"):
                block[j] = rendered
                break
        else:
            block.append(rendered)
    lines[mi + 1 : block_end] = block
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("---\n" + "\n".join(lines) + tail)


def digest(store: Store, cwd: str, today: Optional[_dt.date] = None) -> list:
    slug = cwd_slug(cwd)
    files = memory_files(store.worktree, slug)
    if not files:
        return []
    rows = triage_rows(store.worktree, slug, today)
    stale = [r["file"] for r in rows if any(w.startswith("stale since") for w in r["warnings"])]
    missing = [r["file"] for r in rows if any("stale_after" in w and "required" in w for w in r["warnings"])]
    lines = [f"Memory: {len(files)} files for this project"]
    if store.exists():
        r = store.git(["log", "--format=%ad %s", "--date=short", "-n3", "--", f"{slug}/memory"], check=False)
        recent = [ln for ln in r.stdout.splitlines() if ln.strip()]
        if recent:
            lines.append("Recent memory commits: " + " | ".join(recent)[:300])
    if stale:
        lines.append("Stale (re-verify or deprecate): " + ", ".join(stale[:4]) + (" …" if len(stale) > 4 else ""))
    if missing:
        lines.append(f"Without stale_after ({len(missing)}): run memstore.py triage")
    out, size = [], 0
    for ln in lines[:DIGEST_MAX_LINES]:
        if size + len(ln) + 1 > DIGEST_MAX_BYTES:
            break
        out.append(ln)
        size += len(ln) + 1
    return out


def is_copilot(raw: dict) -> bool:
    """Same tell the guard uses: Copilot payloads carry `timestamp` or camelCase keys, Claude Code's never do."""
    return "timestamp" in raw or "toolName" in raw or "toolArgs" in raw


def hook(store: Store, stdin, err) -> int:
    """PostToolUse: commit the written memory file, then validate it. Exit 2 = schema feedback for the agent.
    Claude Code only; Copilot payloads and paths outside the work tree return 0 silently."""
    try:
        raw = json.loads(stdin.read() or "{}")
    except ValueError:
        return 0
    if not isinstance(raw, dict) or is_copilot(raw):
        return 0
    ti = raw.get("tool_input") if isinstance(raw.get("tool_input"), dict) else {}
    path = ti.get("file_path") or ti.get("path") or ""
    if not path or store.memory_rel(path) is None:
        return 0
    try:
        store.commit(path, err)
    except RuntimeError as exc:  # e.g. a lock held by a parallel hook: the next write catches up
        err.write(f"memstore: commit skipped: {exc}\n")
    full = os.path.expanduser(path)
    if os.path.basename(full) == "MEMORY.md" or not os.path.exists(full):  # the index has no frontmatter by design
        return 0
    warnings = validate_file(full)
    if warnings:
        err.write("memory schema: " + os.path.basename(path) + ": " + "; ".join(warnings) + "\n")
        return 2
    return 0


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------


def main(argv: list, out=None, err=None, stdin=None) -> int:
    out, err, stdin = out or sys.stdout, err or sys.stderr, stdin or sys.stdin
    ap = argparse.ArgumentParser(prog="memstore", add_help=False)
    ap.add_argument("--store")
    ap.add_argument("--worktree")
    sub = ap.add_subparsers(dest="verb")
    sub.add_parser("init")
    sub.add_parser("hook")
    s = sub.add_parser("commit")
    s.add_argument("path")
    sub.add_parser("push")
    s = sub.add_parser("digest")
    s.add_argument("--cwd", default=os.getcwd())
    s = sub.add_parser("log")
    s.add_argument("-n", type=int, default=10)
    s = sub.add_parser("validate")
    s.add_argument("files", nargs="+")
    s = sub.add_parser("index")
    s.add_argument("--cwd", default=os.getcwd())
    s.add_argument("--write", action="store_true")
    s = sub.add_parser("triage")
    s.add_argument("--cwd", default=os.getcwd())
    s = sub.add_parser("deprecate")
    s.add_argument("file")
    s.add_argument("--by")
    if not argv or argv[0] in ("help", "-h", "--help"):
        out.write(__doc__.strip() + "\n")
        return 0
    try:
        ns = ap.parse_args(argv)
    except SystemExit:
        return 1
    store = Store(ns.store, ns.worktree)
    try:
        if ns.verb == "init":
            return store.init(out)
        if ns.verb == "commit":
            return store.commit(ns.path, out)
        if ns.verb == "push":
            return store.push(out)
        if ns.verb == "log":
            return store.log(ns.n, out)
        if ns.verb == "hook":
            return hook(store, stdin, err)
        if ns.verb == "digest":
            for ln in digest(store, ns.cwd):
                out.write(ln + "\n")
            return 0
        if ns.verb == "validate":
            bad = 0
            for f in ns.files:
                w = validate_file(f)
                if w:
                    bad += 1
                    err.write(f"{f}: " + "; ".join(w) + "\n")
            return 2 if bad else 0
        if ns.verb == "index":
            text = build_index(store.worktree, cwd_slug(ns.cwd))
            if ns.write:
                target = os.path.join(store.worktree, cwd_slug(ns.cwd), "memory", "MEMORY.md")
                with open(target, "w", encoding="utf-8") as fh:
                    fh.write(text)
                store.commit(target, out)
                out.write(f"wrote {target} ({len(text)} bytes)\n")
            else:
                out.write(text)
            return 0
        if ns.verb == "triage":
            rows = triage_rows(store.worktree, cwd_slug(ns.cwd))
            for r in rows:
                flag = "; ".join(r["warnings"]) if r["warnings"] else "ok"
                out.write(f"{r['status']:<10} {r['type']:<9} {r['stale_after'] or '-':<10} {r['file']:<48} {flag}\n")
            out.write(f"{len(rows)} files, {sum(1 for r in rows if r['warnings'])} with warnings\n")
            return 0
        if ns.verb == "deprecate":
            fields = {"status": "superseded", "superseded_by": ns.by} if ns.by else {"status": "deprecated"}
            set_metadata(ns.file, **fields)
            store.commit(ns.file, out)
            out.write(f"{ns.file}: {fields}\n")
            return 0
    except RuntimeError as exc:
        err.write(f"memstore: error: {exc}\n")
        return 1
    out.write(__doc__.strip() + "\n")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
