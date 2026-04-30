# Running This Repo

This repo has two separate workflows:

1. Build the WRF-augmented dataset and the matched WSTS dataset.
2. Train the model on the resulting Zarr datasets.

## 1. Preferred host-side Podman workflow

If you want to avoid setting up conda directly on the machine, use the Podman container path from the real host, outside distrobox.

Build the image:

```bash
cd /home/lornjaeger/distrobox/homes/train/scratch/WildfireSpreadTS_with_wrf
./scripts/podman_build.sh
```

Open a shell in the GPU-enabled container:

```bash
./scripts/podman_shell.sh
```

Inside that container, create or update the repo envs once:

```bash
./scripts/podman_setup_envs.sh
```

Then use the normal repo commands:

```bash
./scripts/build_all_datasets.sh --workers 8
WANDB_MODE=disabled ./scripts/train_wrf_vs_wsts.sh --fold 0 --epochs 50 --batch 32 --workers 16
```

Notes:

- `scripts/podman_shell.sh` mounts the repo at `/workspace`.
- It mounts host `/run/data_raid5` to `/run/host/run/data_raid5`, matching the repo's hard-coded data paths.
- It uses persistent Podman volumes for `/opt/conda/envs` and `/opt/conda/pkgs`, so envs survive across sessions.
- This is intended to be launched from the real host, not from inside the distrobox.

## 2. Direct conda env setup

The helper scripts expect conda env names `build` and `train`.
The checked-in YAML files are named `wsts_join` and `wsts_wrf_gpu`, so the easiest path is to create the envs with overridden names:

```bash
cd /home/lornjaeger/distrobox/homes/train/scratch/WildfireSpreadTS_with_wrf

conda env create -f environment-joining.yml -n build
conda env create -f environment.yml -n train
```

If those envs already exist:

```bash
conda env update -f environment-joining.yml -n build --prune
conda env update -f environment.yml -n train --prune
```

Notes:

- `build` is for preprocessing / dataset joining.
- `train` is for GPU training.
- `scripts/run_in_project_env.sh` enters distrobox `train` by default, then runs `conda run -n ...`.
- If WRF NetCDF reading fails in preprocessing, install `wrf-python` into `build`.

## 3. Expected data locations

The current helper scripts are hard-coded to these paths:

```text
SOURCE_WSTS=/run/host/run/data_raid5/shared_data/WSTS
WRF_NETCDF=/run/host/run/data_raid5/lornjaeger/trimmed
WRF_OUT_DIR=/run/host/run/data_raid5/scratch/wrf_wsts
WRF_ZARR_DIR=/run/host/run/data_raid5/scratch/wrf_wsts_zarr
MATCH_DIR=/run/host/run/data_raid5/scratch/wrf_wsts_match
MATCH_ZARR_DIR=/run/host/run/data_raid5/scratch/wrf_wsts_zarr_match
```

What gets built:

- `wrf_wsts`: WSTS TIFFs enriched with WRF variables.
- `wrf_wsts_zarr`: Zarr version of `wrf_wsts`.
- `wrf_wsts_match`: original WSTS restricted to the same fire-days present in `wrf_wsts`.
- `wrf_wsts_zarr_match`: Zarr version of `wrf_wsts_match`.

## 4. Build all datasets

From the repo root:

```bash
./scripts/build_all_datasets.sh
```

Useful variants:

```bash
./scripts/build_all_datasets.sh --workers 8
./scripts/build_all_datasets.sh --workers 8 --overwrite
```

What this script does:

1. Runs `src/preprocess/BuildWRFWSTS.py`
2. Runs `src/preprocess/BuildMatchedWSTS.py --make_zarr`
3. Runs `src/preprocess/CreateZarrDataset.py` for the WRF-enriched dataset

Important behavior in the WRF join step:

- It looks for WRF files under each fire directory, usually under a `wrf/` subdir.
- It averages multiple WRF files from the same day.
- It uses both the current day and the next day.
- If either the current day or next day WRF data is missing, that TIFF is skipped.

## 5. Rebuild only the matched WSTS side

If `wrf_wsts` already exists and you only need the matched original WSTS plus Zarr outputs:

```bash
./scripts/build_hdf5_match_only.sh
```

Despite the old script name, it now builds matched WSTS plus Zarr outputs, not just HDF5.

## 6. Train the comparison run: WRF first, then matched WSTS

The main remembered command is:

```bash
./scripts/train_wrf_vs_wsts.sh --fold 0 --epochs 50 --batch 32 --workers 16
```

That script trains two runs back-to-back with identical settings:

1. WRF-enriched dataset from `/run/host/run/data_raid5/scratch/wrf_wsts_zarr`
2. Matched WSTS dataset from `/run/host/run/data_raid5/scratch/wrf_wsts_zarr_match`

Defaults in the script:

```text
fold=0
epochs=50
batch=32
workers=16
```

Model/config used by that script:

- Model config: `cfgs/unet/res18_monotemporal.yaml`
- Trainer config: `cfgs/trainer_single_gpu.yaml`
- WRF data config: `cfgs/data_monotemporal_wrf_full_features.yaml`
- Matched WSTS data config: `cfgs/data_monotemporal_full_features.yaml`

This is a 1-day input ResNet18 U-Net run with spatial splitting.

## 7. Run a single training job manually

If you only want one training run instead of the paired comparison script:

WRF dataset:

```bash
PYTHONPATH="$PWD:$PWD/src" WANDB_MODE=disabled conda run -n train \
  python src/train.py \
  --config=cfgs/unet/res18_monotemporal.yaml \
  --trainer=cfgs/trainer_single_gpu.yaml \
  --data=cfgs/data_monotemporal_wrf_full_features.yaml \
  --data.data_dir /run/host/run/data_raid5/scratch/wrf_wsts_zarr \
  --trainer.max_epochs 50 \
  --data.batch_size 32 \
  --data.num_workers 16 \
  --trainer.default_root_dir /tmp/lightning_logs \
  --data.split_strategy spatial \
  --data.data_fold_id 0 \
  --do_train True
```

Matched original WSTS:

```bash
PYTHONPATH="$PWD:$PWD/src" WANDB_MODE=disabled conda run -n train \
  python src/train.py \
  --config=cfgs/unet/res18_monotemporal.yaml \
  --trainer=cfgs/trainer_single_gpu.yaml \
  --data=cfgs/data_monotemporal_full_features.yaml \
  --data.data_dir /run/host/run/data_raid5/scratch/wrf_wsts_zarr_match \
  --trainer.max_epochs 50 \
  --data.batch_size 32 \
  --data.num_workers 16 \
  --trainer.default_root_dir /tmp/lightning_logs \
  --data.split_strategy spatial \
  --data.data_fold_id 0 \
  --do_train True
```

## 8. W&B

The trainer config uses a WandB logger by default.

If you do not want WandB syncing, run with:

```bash
WANDB_MODE=disabled
```

Example:

```bash
WANDB_MODE=disabled ./scripts/train_wrf_vs_wsts.sh --fold 0 --epochs 50 --batch 32 --workers 16
```

## 9. What to remember next time

If you only need the shortest version:

```bash
cd /home/lornjaeger/distrobox/homes/train/scratch/WildfireSpreadTS_with_wrf

./scripts/podman_build.sh
./scripts/podman_shell.sh

# inside the container
./scripts/podman_setup_envs.sh

./scripts/build_all_datasets.sh --workers 8

WANDB_MODE=disabled ./scripts/train_wrf_vs_wsts.sh --fold 0 --epochs 50 --batch 32 --workers 16
```
