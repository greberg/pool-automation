#!/bin/bash
# Bumps patch version in manifest.json after a successful push to main.

INPUT=$(cat)
CMD=$(echo "$INPUT" | jq -r '.tool_input.command // ""')

# Only act on actual push commands
echo "$CMD" | grep -q 'push' || exit 0

# Avoid infinite loop: skip if the last commit is already a version bump
REPO="/Users/peter.greberg/Documents/pool-monitor"
LAST_MSG=$(git -C "$REPO" log -1 --format=%s 2>/dev/null || echo "")
echo "$LAST_MSG" | grep -q "^chore: bump version" && exit 0

MANIFEST="$REPO/custom_components/pool_automation/manifest.json"
CURRENT=$(jq -r '.version' "$MANIFEST")
NEW=$(python3 -c "v='$CURRENT'.split('.'); v[2]=str(int(v[2])+1); print('.'.join(v))")

TMP=$(mktemp)
jq --arg v "$NEW" '.version = $v' "$MANIFEST" > "$TMP" && mv "$TMP" "$MANIFEST"

git -C "$REPO" add custom_components/pool_automation/manifest.json
git -C "$REPO" commit -m "chore: bump version to $NEW"
git -C "$REPO" push origin HEAD:main
