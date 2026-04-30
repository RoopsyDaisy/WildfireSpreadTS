#!/usr/bin/env bash
set -euo pipefail


REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/run_in_project_env.sh"

SOURCE_WSTS="/run/host/run/data_raid5/shared_data/WSTS"
WRF_OUT_DIR="/run/host/run/data_raid5/scratch/wrf_wsts"
WRF_ZARR_DIR="/run/host/run/data_raid5/scratch/wrf_wsts_zarr"
MATCH_DIR="/run/host/run/data_raid5/scratch/wrf_wsts_match"
MATCH_ZARR_DIR="/run/host/run/data_raid5/scratch/wrf_wsts_zarr_match"
WRF_NETCDF="/run/host/run/data_raid5/lornjaeger/trimmed"

WORKERS=0
OVERWRITE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workers)
      WORKERS="$2"
      shift 2
      ;;
    --overwrite)
      OVERWRITE=1
      shift 1
      ;;
    *)
      echo "Unknown arg: $1"
      exit 1
      ;;
  esac
done

cd "$REPO_ROOT"

mkdir -p "$WRF_OUT_DIR" "$WRF_ZARR_DIR" "$MATCH_DIR" "$MATCH_ZARR_DIR"

OVERWRITE_FLAG=""
if [[ "$OVERWRITE" -eq 1 ]]; then
  OVERWRITE_FLAG="--overwrite"
fi

WORKER_FLAG=""
if [[ "$WORKERS" -gt 0 ]]; then
  WORKER_FLAG="--workers $WORKERS"
fi

echo "[1/3] Building WRF-enriched TIFFs"
run_in_project_env build python src/preprocess/BuildWRFWSTS.py \
  --wsts_dir "$SOURCE_WSTS" \
  --wrf_dir "$WRF_NETCDF" \
  --out_dir "$WRF_OUT_DIR" \
  $OVERWRITE_FLAG \
  $WORKER_FLAG

echo "[2/3] Building matched WSTS (same days as WRF) + Zarr"
run_in_project_env build python src/preprocess/BuildMatchedWSTS.py \
  --source_wsts "$SOURCE_WSTS" \
  --reference_wrf "$WRF_OUT_DIR" \
  --out_dir "$MATCH_DIR" \
  --zarr_dir "$MATCH_ZARR_DIR" \
  --make_zarr

echo "[3/3] Building WRF Zarr"
run_in_project_env build python src/preprocess/CreateZarrDataset.py \
  --data_dir "$WRF_OUT_DIR" \
  --target_dir "$WRF_ZARR_DIR"

echo "Done."
