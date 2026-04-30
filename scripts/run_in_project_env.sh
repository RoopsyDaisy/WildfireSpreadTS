#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
PROJECT_DBOX_NAME="${PROJECT_DBOX_NAME:-train}"
PROJECT_DBOX_REPO_ROOT="${PROJECT_DBOX_REPO_ROOT:-/home/lornjaeger/distrobox/homes/train/scratch/WildfireSpreadTS_with_wrf}"

run_in_project_env() {
  local env_name="$1"
  shift
  local pythonpath="$REPO_ROOT:$REPO_ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

  if [[ -f /run/.containerenv || -f /.dockerenv || "${PROJECT_IN_CONTAINER:-}" == "1" ]]; then
    (
      cd "$REPO_ROOT"
      env PYTHONPATH="$pythonpath" conda run -n "$env_name" "$@"
    )
    return
  fi

  local quoted_cmd=""
  printf -v quoted_cmd '%q ' "$@"
  distrobox enter "$PROJECT_DBOX_NAME" -- bash -lc \
    "cd '$PROJECT_DBOX_REPO_ROOT' && env PYTHONPATH='$PROJECT_DBOX_REPO_ROOT:$PROJECT_DBOX_REPO_ROOT/src' conda run -n '$env_name' ${quoted_cmd}"
}
