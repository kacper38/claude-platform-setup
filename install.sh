#!/usr/bin/env bash
# Install this Claude Code setup into ~/.claude (user scope).
# Usage:
#   ./install.sh              install (backs up any files it would overwrite)
#   ./install.sh --uninstall  remove everything listed in the install manifest
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="${CLAUDE_DIR:-$HOME/.claude}"
MANIFEST="$DEST/claude-platform-setup.manifest"

if [[ "${1:-}" == "--uninstall" ]]; then
  if [[ ! -f "$MANIFEST" ]]; then
    echo "No manifest at $MANIFEST — nothing to uninstall." >&2
    exit 1
  fi
  while IFS= read -r f; do
    [[ -z "$f" || "$f" == \#* ]] && continue
    rm -f "$DEST/$f"
  done < "$MANIFEST"
  find "$DEST/skills" "$DEST/agents" -type d -empty -delete 2>/dev/null || true
  rm -f "$MANIFEST"
  echo "Uninstalled. Backups, if any, remain in $DEST/backups/."
  exit 0
fi

mkdir -p "$DEST/agents" "$DEST/skills"

# File list, relative to both $HERE and $DEST
files=()
for a in "$HERE"/agents/*.md; do
  files+=("agents/$(basename "$a")")
done
while IFS= read -r -d '' s; do
  files+=("skills/${s#"$HERE"/skills/}")
done < <(find "$HERE/skills" -type f -print0)

# Back up anything that exists and differs, then copy
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$DEST/backups/claude-platform-setup-$STAMP"
backed_up=0
for f in "${files[@]}"; do
  if [[ -f "$DEST/$f" ]] && ! cmp -s "$HERE/$f" "$DEST/$f"; then
    mkdir -p "$BACKUP/$(dirname "$f")"
    cp "$DEST/$f" "$BACKUP/$f"
    backed_up=$((backed_up + 1))
  fi
  mkdir -p "$DEST/$(dirname "$f")"
  cp "$HERE/$f" "$DEST/$f"
done

{
  echo "# claude-platform-setup — installed $(date -u +%Y-%m-%dT%H:%M:%SZ) @ $(git -C "$HERE" rev-parse --short HEAD 2>/dev/null || echo unknown)"
  printf '%s\n' "${files[@]}"
} > "$MANIFEST"

echo "Installed ${#files[@]} files to $DEST (manifest: $MANIFEST)"
if [[ $backed_up -gt 0 ]]; then
  echo "Backed up $backed_up differing file(s) to $BACKUP"
fi
echo ""
echo "  agents: $(ls "$HERE/agents" | sed 's/\.md$//' | tr '\n' ' ')"
echo "  skills: $(ls "$HERE/skills" | tr '\n' ' ')"
echo ""
echo "New task: start Claude Code in the task repo and run /task-intake."
echo "Working agreement to copy into the task repo: $HERE/CLAUDE.md"
