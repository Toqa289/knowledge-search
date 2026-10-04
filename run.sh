#!/usr/bin/env bash
# Build the search pages and open the chatbot (macOS / Linux).
set -e
cd "$(dirname "$0")"
echo "Building the search pages (preprocess.py)..."
python3 preprocess.py
echo "Opening the chatbot..."
if command -v open >/dev/null 2>&1; then open output/chat.html
elif command -v xdg-open >/dev/null 2>&1; then xdg-open output/chat.html
else echo "Open output/chat.html in your browser."; fi
