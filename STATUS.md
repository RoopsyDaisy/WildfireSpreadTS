# Project status

Living doc — overwrites encouraged, history in git. Pair with [docs/BACKLOG.md](docs/BACKLOG.md)
for non-urgent ideas / cleanup work and [CLAUDE.md](CLAUDE.md) for working principles.

**Last updated:** 2026-05-13

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

## Headline dry-run metrics (fold 0, 100 epochs)

| Metric | 2026-05-08 baseline | 2026-05-10 with fix | Δ |
|---|---|---|---|
| **test_loss** | **1.80e+30** | **0.00364** | **fixed (10³² ratio)** |
| test_AP | 0.522 | 0.527 | +0.005 |
| val_avg_precision (best) | 0.480 (ep 93) | 0.490 (ep 87) | +0.010 |
| test_f1 | 0.511 | 0.492 | -0.019 |
| test_iou | 0.343 | 0.326 | -0.017 |
| test_precision | 0.655 | 0.684 | +0.029 |
| test_recall | 0.419 | 0.384 | -0.035 |

Fix was three things in one commit (`498e9d9`): recompute WRF-channel
standardization stats (the baked-in ones were for original WSTS GRIDMET / GFS
data), add a load-time clip for NetCDF sentinel-fill values that leak into ch
5 / 17 for two fires, and gate both behind a new `wrf_data: bool` flag on the
data config so the matched-WSTS comparison run is unaffected. AP and val are
basically unchanged; model is slightly more conservative (precision up, recall
down) but rank-ordering of predictions is the same. Pre-fix, the model was
effectively compensating for bad standardization.

Best checkpoint (persists across container restarts):
`/run/data_raid5/scratch/lightning_logs/wildfire_progression/qdubpkl0/checkpoints/best-epoch=87-val_avg_precision=0.49.ckpt`

## Known broken / not yet validated

- **`scripts/build_all_datasets.sh` and `scripts/build_hdf5_match_only.sh`** were ported
  from lorn's distrobox+conda flow to the devcontainer's uv venv but have not been
  re-run end-to-end. The scratch datasets they produce already exist, so this hasn't
  blocked anyone yet. Expect to debug at least the wrf-python build path on first run
  (`uv sync --extra wrf` is required).
- **`~/.netrc` for wandb does not survive a container rebuild.** The `~/.claude/`
  mount persists chat/memory but `~/.netrc` lives outside it. For now, run training
  with `WANDB_MODE=disabled`, or re-`uv run wandb login` after a rebuild.
- **SSH agent forwarding fixed 2026-05-13.** VS Code's auto-injected proxy
  socket is broken on this host; postCreate now pins `SSH_AUTH_SOCK=/ssh-agent`
  for interactive shells via `/etc/profile.d/01-ssh-agent.sh`. Non-interactive
  `sh -c` invocations (e.g. Claude Code's Bash tool) still inherit VS Code's
  bad socket — prefix `SSH_AUTH_SOCK=/ssh-agent` if you need github access
  from such a context. Commit `4d6683f`.

## Audit findings from lorn handover (2026-05-08)

Sent lorn a batch of clarifying questions on his last day; answers below, plus
what we found by digging.

1. **`test_loss = 1.8e+30`** — lorn: "no idea." **Resolved 2026-05-10** in
   commit `498e9d9`. Root cause: two fires (`2018/fire_22258421`,
   `2021/fire_25294687`) had NetCDF sentinel-fill pixels (~1e+36) in
   channels 5 / 17 from `BuildWRFWSTS.py` averaging files without
   filtering. Combined with stale standardization stats (next bullet),
   these blew up one or two test batches' focal loss into the 1e+30 range.
   Fix: recompute WRF stats with sentinel filter + apply load-time clip.
   New test_loss = 0.00364.
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

### Real bugs surfaced by the audits

- **Standardization stats were stale for WRF channels** — `get_means_stds_missing_values()`
  returned hardcoded values computed on original WSTS GRIDMET / GFS data, but
  those channels now hold WRF data with different distributions. **Resolved
  2026-05-10** in commit `498e9d9`: new `src/dataloader/wrf_stats.py` plus a
  `wrf_data: bool` flag on the data config. Recompute script lives at
  `scripts/compute_wrf_stats.py` for future migrations.

- **NetCDF sentinel-fill values (~1e+36) leak into ch 5 / 17 for 2 fires** —
  caused by `BuildWRFWSTS.py.average_wrf_files` not filtering the NetCDF
  `_FillValue` before summing. **Resolved 2026-05-10** with a load-time clip
  in `FireSpreadDataset.preprocess_and_augment` (gated on `wrf_data: bool`).
  Doesn't fix the upstream preprocessing — that's still a backlog item for
  the next BuildWRFWSTS re-run.

## Open questions for Rupert / colleague

- **Where do datasets live long-term?** Decision (2026-05-07) is to migrate from
  `/run/data_raid5/scratch/` to `/run/data_raid5/shared_data/wrf_wsts/` — see
  backlog. Not yet executed.
- **Does the new colleague need their own host account?** Affects whether `~/.claude/`
  and SSH key setup story is per-user or shared.

## Recent changes

- 2026-05-13 — Resolved SSH agent forwarding (host vs. VS Code proxy mismatch).
  postCreate now installs a `/etc/profile.d/` override. Commit `4d6683f`.
- 2026-05-10 — Resolved `test_loss = 1.8e+30` anomaly. Added WRF-specific
  standardization stats (`src/dataloader/wrf_stats.py` + recompute script),
  a load-time clip for NetCDF sentinel-fill values, and a `wrf_data: bool`
  flag on the data config. Bumped checkpoint default to a persistent path.
  Commit `498e9d9`.
- 2026-05-08 — Audited the three open lorn-questions; channel mapping verified,
  stale-stats bug surfaced, dead-end fires identified for deletion (deferred to
  host shell). Commit `bc0c9fc`.
- 2026-05-08 — Bumped Python 3.10→3.12, zarr <3.0→>=3.0.8 (data on disk is v3 format),
  fixed three pipeline bugs (wandb_setup guard, `len(zarr_array)` v3 incompat,
  optional SegFormer import). Commit `8db2e69`.
- 2026-05-08 — Ported `train_wrf_vs_wsts.sh` to the devcontainer's uv flow; deleted
  `run_in_project_env.sh` and the `podman_*.sh` scripts that targeted lorn's
  host-side distrobox setup. Build scripts ported but unverified. Commit `07bc189`.
- 2026-05-07 — Devcontainer postCreate failure (wrf-python build dep) fixed by
  declaring numpy as an extra-build-dep for wrf-python. Commit `11731ae`.
