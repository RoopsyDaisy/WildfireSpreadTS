#!/usr/bin/env bash
set -euo pipefail

# Legacy script name (despite "hdf5", this builds matched WSTS + Zarr).
# Use when wrf_wsts/ already exists and you only need to refresh the matched
# original WSTS subset and its Zarr companion.
#
# Runs inside the devcontainer's uv-managed venv.
#
# WARNING: ported from lorn's distrobox+conda flow but UNTESTED in the
# devcontainer. See build_all_datasets.sh for the same caveat and
# docs/BACKLOG.md for related cleanup.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SOURCE_WSTS="${SOURCE_WSTS:-/run/data_raid5/shared_data/WSTS}"
WRF_OUT_DIR="${WRF_OUT_DIR:-/run/data_raid5/scratch/wrf_wsts}"
WRF_ZARR_DIR="${WRF_ZARR_DIR:-/run/data_raid5/scratch/wrf_wsts_zarr}"
MATCH_DIR="${MATCH_DIR:-/run/data_raid5/scratch/wrf_wsts_match}"
MATCH_ZARR_DIR="${MATCH_ZARR_DIR:-/run/data_raid5/scratch/wrf_wsts_zarr_match}"

mkdir -p "$MATCH_DIR" "$MATCH_ZARR_DIR" "$WRF_ZARR_DIR"

run_step() {
  echo "=== $1 ==="
  shift
  PYTHONPATH="$REPO_ROOT:$REPO_ROOT/src" uv run python "$@"
}

run_step "[1/2] Building matched WSTS (same days as WRF) + Zarr" \
  src/preprocess/BuildMatchedWSTS.py \
  --source_wsts "$SOURCE_WSTS" \
  --reference_wrf "$WRF_OUT_DIR" \
  --out_dir "$MATCH_DIR" \
  --zarr_dir "$MATCH_ZARR_DIR" \
  --make_zarr

run_step "[2/2] Building WRF Zarr" \
  src/preprocess/CreateZarrDataset.py \
  --data_dir "$WRF_OUT_DIR" \
  --target_dir "$WRF_ZARR_DIR"

echo "Done."
