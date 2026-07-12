#!/usr/bin/env bash
# Install this Claude Code setup into ~/.claude (user scope).
# Usage: git clone https://github.com/kacper38/claude-platform-setup.git && ./claude-platform-setup/install.sh
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
DEST="${CLAUDE_DIR:-$HOME/.claude}"

mkdir -p "$DEST/agents" "$DEST/skills"

cp "$HERE"/agents/*.md "$DEST/agents/"
for s in "$HERE"/skills/*/; do
  name="$(basename "$s")"
  mkdir -p "$DEST/skills/$name"
  cp -R "$s"/. "$DEST/skills/$name/"
done

echo "Installed to $DEST:"
echo "  agents: $(ls "$HERE/agents" | sed 's/\.md$//' | paste -sd ', ' -)"
echo "  skills: $(ls "$HERE/skills" | paste -sd ', ' -)"
echo ""
echo "New task: start Claude Code in the task repo and run /task-intake."
echo "Working agreement to copy into the task repo: $HERE/CLAUDE.md"
