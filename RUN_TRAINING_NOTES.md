# Running this repo

This repo has two workflows: **build** the WRF-augmented dataset, and **train**
the model on the resulting Zarr stores. Both run inside the devcontainer's
uv-managed venv.

For status and known issues see [STATUS.md](STATUS.md). For cleanup items see
[docs/BACKLOG.md](docs/BACKLOG.md).

---

## 1. Quick start

```bash
# Sync the env (auto on container create/start; only re-run after pyproject changes)
uv sync

# Confirm GPU
uv run python -c "import torch; print(torch.cuda.is_available(), torch.cuda.device_count())"

# Smoke-test training (5 epochs, ~1 min on a single 4090)
WANDB_MODE=disabled scripts/train_wrf_vs_wsts.sh --fold 0 --epochs 5 --wrf-only

# Real run (100 epochs, ~7 min on a single 4090)
WANDB_MODE=disabled scripts/train_wrf_vs_wsts.sh --fold 0 --epochs 100
```

`WANDB_MODE=disabled` skips wandb auth — useful in dev. Drop it (and run
`uv run wandb login` first) for tracked runs. See [docs/BACKLOG.md](docs/BACKLOG.md)
for the open item on persisting wandb auth across container rebuilds.

---

## 2. Data locations

The devcontainer bind-mounts `/run/data_raid5` from the host. Canonical paths:

| Path | Contents |
|---|---|
| `/run/data_raid5/shared_data/WSTS` | source WSTS TIFFs (read-only by convention) |
| `/run/data_raid5/lornjaeger/trimmed` | source WRF NetCDFs |
| `/run/data_raid5/scratch/wrf_wsts/` | WSTS TIFFs enriched with WRF variables |
| `/run/data_raid5/scratch/wrf_wsts_zarr/` | Zarr v3 of `wrf_wsts/` — main training input |
| `/run/data_raid5/scratch/wrf_wsts_match/` | WSTS subset matching WRF days |
| `/run/data_raid5/scratch/wrf_wsts_zarr_match/` | Zarr v3 of `wrf_wsts_match/` — control run input |

The scripts hardcode `/run/host/run/data_raid5/...` for compatibility with
lorn's podman-host workflow; `postCreate.sh` symlinks that to the real path.
De-hardcoding is a [backlog item](docs/BACKLOG.md).

The `scratch/` paths are slated to migrate to `/run/data_raid5/shared_data/wrf_wsts/`
to escape lorn's per-user scratch convention — also tracked in the backlog.

---

## 3. Training

`scripts/train_wrf_vs_wsts.sh` runs both the WRF-augmented and the matched-WSTS
configs back-to-back with identical settings. Defaults:

| Flag | Default |
|---|---|
| `--fold` | 0 |
| `--epochs` | 50 |
| `--batch` | 32 |
| `--workers` | 16 |
| `--out-dir` | `${LIGHTNING_LOGS_DIR:-/run/data_raid5/scratch/lightning_logs}` (survives container rebuilds) |

Useful flags:

```bash
# Just the WRF run (skip the matched-WSTS comparison)
scripts/train_wrf_vs_wsts.sh --fold 0 --epochs 100 --wrf-only

# Override data paths via env vars (handy after the dataset migration)
WRF_ZARR_DIR=/somewhere/else scripts/train_wrf_vs_wsts.sh --fold 0 --epochs 100
```

Underlying configs:

- Model: [cfgs/unet/res18_monotemporal.yaml](cfgs/unet/res18_monotemporal.yaml) — ResNet18 U-Net, focal loss
- Trainer: [cfgs/trainer_single_gpu.yaml](cfgs/trainer_single_gpu.yaml) — 1 GPU, FP32, wandb logger
- WRF data: [cfgs/data_monotemporal_wrf_full_features.yaml](cfgs/data_monotemporal_wrf_full_features.yaml) — 1-day input, 23 features, spatial split
- Matched WSTS data: [cfgs/data_monotemporal_full_features.yaml](cfgs/data_monotemporal_full_features.yaml)

### Manual single run

If you don't want the paired comparison and prefer to drive `train.py` directly:

```bash
WANDB_MODE=disabled PYTHONPATH="$PWD:$PWD/src" uv run python src/train.py \
  --config=cfgs/unet/res18_monotemporal.yaml \
  --trainer=cfgs/trainer_single_gpu.yaml \
  --data=cfgs/data_monotemporal_wrf_full_features.yaml \
  --data.data_dir /run/data_raid5/scratch/wrf_wsts_zarr \
  --trainer.max_epochs 100 \
  --data.batch_size 32 \
  --data.num_workers 16 \
  --trainer.default_root_dir /tmp/lightning_logs \
  --data.split_strategy spatial \
  --data.data_fold_id 0 \
  --do_train True
```

---

## 4. Building datasets

⚠ The build scripts (`build_all_datasets.sh`, `build_hdf5_match_only.sh`) were
ported from lorn's distrobox+conda flow to the devcontainer's uv venv but
**have not been re-validated end-to-end**. The scratch outputs already exist,
so this hasn't blocked anyone. Expect to debug the `wrf-python` build path
and possibly WRF NetCDF reads on first run.

```bash
# wrf-python is gated behind the [wrf] extra
uv sync --extra wrf

# Build everything end-to-end (1: WRF TIFFs, 2: matched WSTS + Zarr, 3: WRF Zarr)
scripts/build_all_datasets.sh --workers 8

# Just the matched-WSTS side (if wrf_wsts/ already exists)
scripts/build_hdf5_match_only.sh
```

What the WRF-join step does:

- Looks for WRF files under each fire dir's `wrf/` subdir
- Averages multiple WRF files from the same day
- Uses both current-day and next-day WRF data
- Skips a TIFF if either current or next-day WRF is missing

---

## 5. Long-running jobs that survive disconnects

For runs you don't want tied to your shell session:

```bash
LOG=/tmp/dryrun_$(date +%Y%m%d_%H%M%S).log
setsid nohup env WANDB_MODE=disabled \
  scripts/train_wrf_vs_wsts.sh --fold 0 --epochs 500 \
  > "$LOG" 2>&1 < /dev/null &
echo "PID $! → $LOG"
disown
```

`setsid` puts the process in a new session detached from your terminal, so it
survives anything short of the host rebooting. Check progress with `tail -f`,
stop with `kill <pid>`.
