#!/bin/bash
set -e

cd "$(dirname "$0")"
source "../.env"

echo "Posting to settings API..."
python3 system-prompt-helper.py
