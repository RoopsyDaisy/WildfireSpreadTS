# Project status

Living doc — overwrites encouraged, history in git. Pair with [docs/BACKLOG.md](docs/BACKLOG.md)
for non-urgent ideas / cleanup work and [CLAUDE.md](CLAUDE.md) for working principles.

**Last updated:** 2026-05-08

---

## Where we are

- ✅ **Devcontainer is the canonical dev environment.** `uv sync` on container create
  produces a working venv (Python 3.12, torch 2.6+cu124).
- ✅ **End-to-end training works.** Verified by a 100-epoch dry run on the WRF-augmented
  monotemporal config (fold 0, batch 32, 16 workers) — completed in ~7 min on a single
  RTX 4090.
- ✅ **Pre-built scratch datasets are present** under `/run/data_raid5/scratch/`:
  `wrf_wsts/`, `wrf_wsts_zarr/`, `wrf_wsts_match/`, `wrf_wsts_zarr_match/` (plus the
  HDF5 variants). Zarr is the format the training pipeline expects.

## Headline dry-run metrics (2026-05-08, fold 0, 100 epochs)

| Metric | Value |
|---|---|
| Best epoch | 93 |
| val_avg_precision | 0.480 |
| test_AP | 0.522 |
| test_f1 | 0.511 |
| test_iou | 0.343 |
| test_precision | 0.655 |
| test_recall | 0.419 |
| **test_loss** | **1.80e+30 — anomalous** |

Classification metrics look reasonable. The `test_loss` value is wildly inflated
(focal loss over a sigmoid output should never reach 1e+30) — almost certainly a
single test-time batch with numerical blow-up. The metrics themselves are computed
independently and are unaffected, but the loss reporting is broken in some way.
See "Ask lorn" below.

Best checkpoint: `/tmp/lightning_logs/wildfire_progression/orm6zy8s/checkpoints/best-epoch=93-val_avg_precision=0.48.ckpt`
(local, will not survive a container rebuild — see backlog item on persistent
checkpoint storage).

## Known broken / not yet validated

- **`scripts/build_all_datasets.sh` and `scripts/build_hdf5_match_only.sh`** were ported
  from lorn's distrobox+conda flow to the devcontainer's uv venv but have not been
  re-run end-to-end. The scratch datasets they produce already exist, so this hasn't
  blocked anyone yet. Expect to debug at least the wrf-python build path on first run
  (`uv sync --extra wrf` is required).
- **`~/.netrc` for wandb does not survive a container rebuild.** The `~/.claude/`
  mount persists chat/memory but `~/.netrc` lives outside it. For now, run training
  with `WANDB_MODE=disabled`, or re-`uv run wandb login` after a rebuild.
- **SSH agent forwarding works (socket present) but no keys are loaded.** The
  postCreate hook prints a clear warning. `git push` is blocked until the host-side
  agent forwarding is sorted; local commits are unaffected.

## Ask lorn (2026-05-08 is his last day)

In rough priority order:

1. **`test_loss = 1.8e+30` on the 100-epoch dry run.** Has this happened on his runs?
   Where in the loss-reduction code does he expect numerical blow-up to be caught?
   Suspicion: focal loss on a single batch with degenerate inputs (NaN/inf in WRF
   features, or all-zero labels). Worth checking `BaseModel.test_step` and the
   focal-loss path in `SMPModel`.
2. **Why are `cfgs/data_monotemporal_full_features.yaml` and the WRF-flavoured one
   wired differently** for `data_dir` vs everything else? The training-time CLI
   override pattern works, but it'd help to have his rationale documented.
3. **Are the `_match` datasets the right thing to compare against?** Lorn's notes
   imply yes, but worth a sanity check that "WSTS restricted to the same days where
   WRF was available" is the right control group, not "all of WSTS".

## Open questions for Rupert / colleague

- **Where do datasets live long-term?** Decision (2026-05-07) is to migrate from
  `/run/data_raid5/scratch/` to `/run/data_raid5/shared_data/wrf_wsts/` — see
  backlog. Not yet executed.
- **Does the new colleague need their own host account?** Affects whether `~/.claude/`
  and SSH key setup story is per-user or shared.

## Recent changes

- 2026-05-08 — Bumped Python 3.10→3.12, zarr <3.0→>=3.0.8 (data on disk is v3 format),
  fixed three pipeline bugs (wandb_setup guard, `len(zarr_array)` v3 incompat,
  optional SegFormer import). Commit `8db2e69`.
- 2026-05-08 — Ported `train_wrf_vs_wsts.sh` to the devcontainer's uv flow; deleted
  `run_in_project_env.sh` and the `podman_*.sh` scripts that targeted lorn's
  host-side distrobox setup. Build scripts ported but unverified.
- 2026-05-07 — Devcontainer postCreate failure (wrf-python build dep) fixed by
  declaring numpy as an extra-build-dep for wrf-python. Commit `11731ae`.
