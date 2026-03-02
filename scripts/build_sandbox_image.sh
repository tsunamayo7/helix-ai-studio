#!/bin/bash
# Helix AI Studio — Sandbox Docker イメージビルド
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Building helix-sandbox Docker image..."
docker build -t helix-sandbox:latest -f "$PROJECT_ROOT/docker/sandbox/Dockerfile" "$PROJECT_ROOT/docker/sandbox/"
echo "Done: helix-sandbox:latest"
