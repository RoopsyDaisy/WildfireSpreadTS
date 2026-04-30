#!/usr/bin/env bash
set -euo pipefail

# Legacy script name; now builds matched WSTS (same days as WRF) and both Zarr datasets.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/run_in_project_env.sh"

SOURCE_WSTS="/run/host/run/data_raid5/shared_data/WSTS"
WRF_OUT_DIR="/run/host/run/data_raid5/scratch/wrf_wsts"
WRF_ZARR_DIR="/run/host/run/data_raid5/scratch/wrf_wsts_zarr"
MATCH_DIR="/run/host/run/data_raid5/scratch/wrf_wsts_match"
MATCH_ZARR_DIR="/run/host/run/data_raid5/scratch/wrf_wsts_zarr_match"

cd "$REPO_ROOT"

mkdir -p "$MATCH_DIR" "$MATCH_ZARR_DIR" "$WRF_ZARR_DIR"

echo "[1/2] Building matched WSTS (same days as WRF) + Zarr"
run_in_project_env build python src/preprocess/BuildMatchedWSTS.py \
  --source_wsts "$SOURCE_WSTS" \
  --reference_wrf "$WRF_OUT_DIR" \
  --out_dir "$MATCH_DIR" \
  --zarr_dir "$MATCH_ZARR_DIR" \
  --make_zarr

echo "[2/2] Building WRF Zarr"
run_in_project_env build python src/preprocess/CreateZarrDataset.py \
  --data_dir "$WRF_OUT_DIR" \
  --target_dir "$WRF_ZARR_DIR"

echo "Done."
