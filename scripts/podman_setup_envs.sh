#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

ensure_env() {
  local env_name="$1"
  local env_file="$2"

  if conda env list | awk '{print $1}' | grep -qx "$env_name"; then
    echo "Updating conda env: $env_name"
    conda env update -n "$env_name" -f "$env_file" --prune
  else
    echo "Creating conda env: $env_name"
    conda env create -n "$env_name" -f "$env_file"
  fi
}

ensure_env build environment-joining.yml
ensure_env train environment.yml

echo "Ensuring wrf-python is available in build"
conda run -n build pip install wrf-python

echo "Conda env setup complete."
