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

## Audit findings from lorn handover (2026-05-08)

Sent lorn a batch of clarifying questions on his last day; answers below, plus
what we found by digging.

1. **`test_loss = 1.8e+30`** — lorn: "no idea." We dug:
   - Raw zarr inputs are clean (no NaN/inf, sensible ranges across all 23 channels)
   - Active fire labels are nan-cleaned in `FireSpreadDataset.preprocess_and_augment`
   - Found a related real bug — see "Standardization stats are stale" below
   - Root cause for the 1e+30 magnitude is still unidentified. Needs per-batch
     loss instrumentation in `BaseModel.test_step` to find the offending batch.
2. **5 fires with `RuntimeWarning: ... too few images`** — lorn: "known, not
   fixed, just manual deletion". Verified: each of those fires has 1 WRF-enriched
   TIFF (vs 12-21 in source WSTS) because most days had no current+next WRF data.
   They contribute zero training samples. **Manual deletion deferred** — host-side
   `sudo rm` required because they're owned by `nobody:nogroup` from the
   container's userns-mapped perspective. See backlog item.
3. **23-channel mapping** — lorn: "in the code, double-check it." Verified
   against `FireSpreadDataset.map_channel_index_to_features` (line 640).
   `BuildWRFWSTS.py` overwrites channels 5,6,7,8,9,11,17,18,19,20,21 — these
   exactly correspond to the GRIDMET weather (5-11 except ch 10 = ERC, kept) and
   GFS forecast (17-21) features. The day-vs-next-day asymmetry for temperature
   (ch 8/9 = `t2_min/t2_max` vs ch 20 = plain `t2`) **mirrors the original WSTS
   layout's asymmetry**, not a bug. Strategy is coherent: "replace satellite-derived
   weather with WRF-derived weather".
4. **`_match` baseline correctness** — lorn: confirmed. "wrf fires to wrf fires
   with and without wrf data" = same fires, days where WRF was available. Apples
   to apples.
5. **Hardcoded `np.savez("test_pr_curve_data.npz", ...)`** — lorn: leftover from
   debugging. Already gitignored; backlogged the path fix.
6. **wandb** — lorn: "had it set up but mostly off, generally just saved model
   to disk". Aligns with our `WANDB_MODE=disabled` default.

### Real bugs surfaced by the audits (separate from above)

- **Standardization stats are stale for WRF channels.** `get_means_stds_missing_values()`
  in `dataloader/utils.py` returns hardcoded means/stds computed on the original
  WSTS GRIDMET + GFS values. Channels 5,6,8,9,11,17,18,20,21 now contain WRF
  data with different distributions, but the standardizer doesn't know. Magnitude
  impact looks bounded (no obvious blow-up), but it's a real correctness issue and
  may compound the test_loss anomaly. See backlog.

## Open questions for Rupert / colleague

- **Where do datasets live long-term?** Decision (2026-05-07) is to migrate from
  `/run/data_raid5/scratch/` to `/run/data_raid5/shared_data/wrf_wsts/` — see
  backlog. Not yet executed.
- **Does the new colleague need their own host account?** Affects whether `~/.claude/`
  and SSH key setup story is per-user or shared.

## Recent changes

- 2026-05-08 — Audited the three open lorn-questions; channel mapping verified,
  stale-stats bug surfaced, dead-end fires identified for deletion (deferred to
  host shell). Commit pending.
- 2026-05-08 — Bumped Python 3.10→3.12, zarr <3.0→>=3.0.8 (data on disk is v3 format),
  fixed three pipeline bugs (wandb_setup guard, `len(zarr_array)` v3 incompat,
  optional SegFormer import). Commit `8db2e69`.
- 2026-05-08 — Ported `train_wrf_vs_wsts.sh` to the devcontainer's uv flow; deleted
  `run_in_project_env.sh` and the `podman_*.sh` scripts that targeted lorn's
  host-side distrobox setup. Build scripts ported but unverified. Commit `07bc189`.
- 2026-05-07 — Devcontainer postCreate failure (wrf-python build dep) fixed by
  declaring numpy as an extra-build-dep for wrf-python. Commit `11731ae`.
