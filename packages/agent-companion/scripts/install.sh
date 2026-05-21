#!/usr/bin/env bash
# Install the Logion Marketplace Companion skill.
# Usage: bash scripts/install.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPANION_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILL_FILE="$COMPANION_DIR/SKILL.md"

if [ ! -f "$SKILL_FILE" ]; then
    echo "Error: SKILL.md not found at $SKILL_FILE" >&2
    exit 1
fi

# Validate package structure before installing
python3 "$COMPANION_DIR/scripts/package_skill.py"

INSTALL_BASE="${LOGION_HOME:-$HOME/.logion}"
SKILLS_DIR="$INSTALL_BASE/skills"
TARGET_DIR="$SKILLS_DIR/logion-marketplace-companion"

mkdir -p "$TARGET_DIR"

# Copy skill files
cp "$SKILL_FILE" "$TARGET_DIR/SKILL.md"

# Copy references
if [ -d "$COMPANION_DIR/references" ]; then
    mkdir -p "$TARGET_DIR/references"
    cp -r "$COMPANION_DIR/references/"*.md "$TARGET_DIR/references/"
fi

# Copy course manifest
if [ -d "$COMPANION_DIR/course" ]; then
    mkdir -p "$TARGET_DIR/course"
    cp -r "$COMPANION_DIR/course/"*.yaml "$TARGET_DIR/course/"
fi

echo "Installed Logion Marketplace Companion to $TARGET_DIR"
echo "Rebuilding recall index..."
logion recall index --rebuild 2>/dev/null || echo "Warning: Could not rebuild recall index (Logion CLI may not be installed yet)"

echo "Done."