#!/usr/bin/env bash
set -euo pipefail

# Train WRF dataset first, then matched WSTS dataset with identical settings.
# Usage: scripts/train_wrf_vs_wsts.sh [--fold N] [--epochs N] [--batch N]

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/run_in_project_env.sh"

WRF_ZARR_DIR="/run/host/run/data_raid5/scratch/wrf_wsts_zarr"
WSTS_ZARR_DIR="/run/host/run/data_raid5/scratch/wrf_wsts_zarr_match"

FOLD=0
EPOCHS=50
BATCH=32
WORKERS=16
LOG_EVERY=25

while [[ $# -gt 0 ]]; do
  case "$1" in
    --fold)
      FOLD="$2"
      shift 2
      ;;
    --epochs)
      EPOCHS="$2"
      shift 2
      ;;
    --batch)
      BATCH="$2"
      shift 2
      ;;
    --workers)
      WORKERS="$2"
      shift 2
      ;;
    *)
      echo "Unknown arg: $1"
      exit 1
      ;;
  esac
done

cd "$REPO_ROOT"

COMMON_ARGS=(
  --config=cfgs/unet/res18_monotemporal.yaml
  --trainer=cfgs/trainer_single_gpu.yaml
  --trainer.max_epochs "$EPOCHS"
  --data.batch_size "$BATCH"
  --data.num_workers "$WORKERS"
  --trainer.log_every_n_steps "$LOG_EVERY"
  --trainer.default_root_dir /tmp/lightning_logs
  --data.split_strategy spatial
  --data.data_fold_id "$FOLD"
  --do_train True
)

echo "[1/2] Training WRF dataset"
run_in_project_env train env PYTHONPATH="$REPO_ROOT:$REPO_ROOT/src" python src/train.py \
  --data=cfgs/data_monotemporal_wrf_full_features.yaml \
  --data.data_dir "$WRF_ZARR_DIR" \
  "${COMMON_ARGS[@]}"

echo "[2/2] Training matched WSTS dataset"
run_in_project_env train env PYTHONPATH="$REPO_ROOT:$REPO_ROOT/src" python src/train.py \
  --data=cfgs/data_monotemporal_full_features.yaml \
  --data.data_dir "$WSTS_ZARR_DIR" \
  "${COMMON_ARGS[@]}"

echo "Done."
