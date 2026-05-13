#!/usr/bin/env bash
set -euo pipefail

# Train the WRF-augmented dataset, then the matched original WSTS dataset, with
# identical settings. Runs inside the devcontainer's uv-managed venv; no conda
# or distrobox involvement.
#
# Usage: scripts/train_wrf_vs_wsts.sh [--fold N] [--epochs N] [--batch N]
#                                     [--workers N] [--wrf-only]
#                                     [--out-dir PATH]

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

WRF_ZARR_DIR="${WRF_ZARR_DIR:-/run/data_raid5/scratch/wrf_wsts_zarr}"
WSTS_ZARR_DIR="${WSTS_ZARR_DIR:-/run/data_raid5/scratch/wrf_wsts_zarr_match}"

FOLD=0
EPOCHS=50
BATCH=32
WORKERS=16
LOG_EVERY=25
# Default to a path on the data RAID so checkpoints survive container rebuilds.
# Override via env var or --out-dir.
OUT_DIR="${LIGHTNING_LOGS_DIR:-/run/data_raid5/scratch/lightning_logs}"
WRF_ONLY=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fold)     FOLD="$2"; shift 2 ;;
    --epochs)   EPOCHS="$2"; shift 2 ;;
    --batch)    BATCH="$2"; shift 2 ;;
    --workers)  WORKERS="$2"; shift 2 ;;
    --out-dir)  OUT_DIR="$2"; shift 2 ;;
    --wrf-only) WRF_ONLY=1; shift ;;
    -h|--help)
      sed -n '1,16p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 1
      ;;
  esac
done

mkdir -p "$OUT_DIR"

COMMON_ARGS=(
  --config=cfgs/unet/res18_monotemporal.yaml
  --trainer=cfgs/trainer_single_gpu.yaml
  --trainer.max_epochs "$EPOCHS"
  --data.batch_size "$BATCH"
  --data.num_workers "$WORKERS"
  --trainer.log_every_n_steps "$LOG_EVERY"
  --trainer.default_root_dir "$OUT_DIR"
  --data.split_strategy spatial
  --data.data_fold_id "$FOLD"
  --do_train True
)

run_one() {
  local label="$1" data_cfg="$2" data_dir="$3"
  echo "=== ${label} ==="
  echo "  data_cfg=${data_cfg}"
  echo "  data_dir=${data_dir}"
  PYTHONPATH="$REPO_ROOT:$REPO_ROOT/src" uv run python src/train.py \
    --data="$data_cfg" \
    --data.data_dir "$data_dir" \
    "${COMMON_ARGS[@]}"
}

run_one "[1/2] WRF-augmented" \
  cfgs/data_monotemporal_wrf_full_features.yaml \
  "$WRF_ZARR_DIR"

if [[ "$WRF_ONLY" -eq 1 ]]; then
  echo "Skipping matched WSTS run (--wrf-only)."
  echo "Done."
  exit 0
fi

run_one "[2/2] Matched WSTS" \
  cfgs/data_monotemporal_full_features.yaml \
  "$WSTS_ZARR_DIR"

echo "Done."
