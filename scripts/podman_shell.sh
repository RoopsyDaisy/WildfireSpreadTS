#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="${IMAGE_NAME:-localhost/wsts-wrf:latest}"
CONTAINER_NAME="${CONTAINER_NAME:-wsts-wrf-dev}"
CONDA_ENVS_VOLUME="${CONDA_ENVS_VOLUME:-wsts_wrf_conda_envs}"
CONDA_PKGS_VOLUME="${CONDA_PKGS_VOLUME:-wsts_wrf_conda_pkgs}"
HOST_DATA_ROOT="${HOST_DATA_ROOT:-/run/data_raid5}"
CONTAINER_DATA_ROOT="${CONTAINER_DATA_ROOT:-/run/host/run/data_raid5}"
WANDB_MODE="${WANDB_MODE:-disabled}"

if [[ ! -d "$HOST_DATA_ROOT" ]]; then
  echo "Host data root does not exist: $HOST_DATA_ROOT" >&2
  exit 1
fi

if ! podman image exists "$IMAGE_NAME"; then
  echo "Image $IMAGE_NAME does not exist yet. Build it first with scripts/podman_build.sh" >&2
  exit 1
fi

podman volume exists "$CONDA_ENVS_VOLUME" || podman volume create "$CONDA_ENVS_VOLUME" >/dev/null
podman volume exists "$CONDA_PKGS_VOLUME" || podman volume create "$CONDA_PKGS_VOLUME" >/dev/null

podman run --rm -it \
  --name "$CONTAINER_NAME" \
  --security-opt=label=disable \
  --device nvidia.com/gpu=all \
  --ipc=host \
  --shm-size=16g \
  -e PROJECT_IN_CONTAINER=1 \
  -e WANDB_MODE="$WANDB_MODE" \
  -e PYTHONPATH=/workspace:/workspace/src \
  -e REPO_ROOT=/workspace \
  -v "$REPO_ROOT":/workspace \
  -v "$HOST_DATA_ROOT":"$CONTAINER_DATA_ROOT" \
  -v "$CONDA_ENVS_VOLUME":/opt/conda/envs \
  -v "$CONDA_PKGS_VOLUME":/opt/conda/pkgs \
  -w /workspace \
  "$IMAGE_NAME" \
  bash
