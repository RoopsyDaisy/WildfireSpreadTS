#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="${IMAGE_NAME:-localhost/wsts-wrf:latest}"

podman build -f "$REPO_ROOT/.container/Containerfile" -t "$IMAGE_NAME" "$REPO_ROOT"
