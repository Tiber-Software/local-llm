#!/bin/bash
set -e

cd "$(dirname "$0")"

echo "Reading system prompt..."
SYSTEM_PROMPT=$(cat "../system_prompt.txt")

echo "Escaping sequences..."
SYSTEM_PROMPT_ESCAPED=$(printf '%s\n' "$SYSTEM_PROMPT" | sed 's/\\/\\\\/g' | sed 's/"/\\"/g' | sed ':a;N;$!ba;s/\n/\\n/g')

echo "Updating config/config.yaml..."
# Create a backup
cp "../config/config.yaml" "../config/config.yaml.bak"

# Use awk to replace the entire system_prompt block
awk -v new_prompt="$SYSTEM_PROMPT_ESCAPED" '
/^  system_prompt:/ {
    print "  system_prompt: \"" new_prompt "\""
    # Skip all lines until we hit the next field at same indentation
    while (getline && /^    /) { }
    if (NF > 0) print $0
    next
}
{ print }
' "../config/config.yaml.bak" > "../config/config.yaml"

echo "Done. System prompt updated for sysytem_prompt.txt"

cd ../docker
if docker compose ps | grep -q "Up"; then
    echo "Services running. Restarting..."
    docker compose --env-file ../.env down -v
    docker compose --env-file ../.env up -d
fi

echo "Done."
