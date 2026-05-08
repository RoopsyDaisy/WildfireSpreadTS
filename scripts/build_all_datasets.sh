#!/usr/bin/env bash
set -euo pipefail

# Build the full WRF + matched WSTS dataset chain end-to-end:
#   1. WRF-enriched TIFFs (BuildWRFWSTS.py — needs the [wrf] extra)
#   2. Matched WSTS TIFFs + Zarr  (BuildMatchedWSTS.py)
#   3. WRF Zarr                   (CreateZarrDataset.py)
#
# Runs inside the devcontainer's uv-managed venv. wrf-python is gated behind
# the [wrf] extra in pyproject.toml; install it first if step 1 fails:
#     uv sync --extra wrf
#
# WARNING: ported from lorn's distrobox+conda flow but UNTESTED in the
# devcontainer. The path replacements look right and the tools are in the
# uv env, but expect to debug at least the wrf-python build / WRF NetCDF
# read path on first run. If you hit issues, see docs/BACKLOG.md for the
# de-hardcode-paths item that's adjacent to this work.

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

SOURCE_WSTS="${SOURCE_WSTS:-/run/data_raid5/shared_data/WSTS}"
WRF_OUT_DIR="${WRF_OUT_DIR:-/run/data_raid5/scratch/wrf_wsts}"
WRF_ZARR_DIR="${WRF_ZARR_DIR:-/run/data_raid5/scratch/wrf_wsts_zarr}"
MATCH_DIR="${MATCH_DIR:-/run/data_raid5/scratch/wrf_wsts_match}"
MATCH_ZARR_DIR="${MATCH_ZARR_DIR:-/run/data_raid5/scratch/wrf_wsts_zarr_match}"
WRF_NETCDF="${WRF_NETCDF:-/run/data_raid5/lornjaeger/trimmed}"

WORKERS=0
OVERWRITE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --workers)   WORKERS="$2"; shift 2 ;;
    --overwrite) OVERWRITE=1; shift 1 ;;
    -h|--help)   sed -n '1,18p' "$0"; exit 0 ;;
    *)           echo "Unknown arg: $1" >&2; exit 1 ;;
  esac
done

mkdir -p "$WRF_OUT_DIR" "$WRF_ZARR_DIR" "$MATCH_DIR" "$MATCH_ZARR_DIR"

OVERWRITE_FLAG=""
[[ "$OVERWRITE" -eq 1 ]] && OVERWRITE_FLAG="--overwrite"

WORKER_FLAG=""
[[ "$WORKERS" -gt 0 ]] && WORKER_FLAG="--workers $WORKERS"

run_step() {
  echo "=== $1 ==="
  shift
  PYTHONPATH="$REPO_ROOT:$REPO_ROOT/src" uv run python "$@"
}

run_step "[1/3] Building WRF-enriched TIFFs" \
  src/preprocess/BuildWRFWSTS.py \
  --wsts_dir "$SOURCE_WSTS" \
  --wrf_dir "$WRF_NETCDF" \
  --out_dir "$WRF_OUT_DIR" \
  $OVERWRITE_FLAG \
  $WORKER_FLAG

run_step "[2/3] Building matched WSTS (same days as WRF) + Zarr" \
  src/preprocess/BuildMatchedWSTS.py \
  --source_wsts "$SOURCE_WSTS" \
  --reference_wrf "$WRF_OUT_DIR" \
  --out_dir "$MATCH_DIR" \
  --zarr_dir "$MATCH_ZARR_DIR" \
  --make_zarr

run_step "[3/3] Building WRF Zarr" \
  src/preprocess/CreateZarrDataset.py \
  --data_dir "$WRF_OUT_DIR" \
  --target_dir "$WRF_ZARR_DIR"

echo "Done."
