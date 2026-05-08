# Backlog

Tangential improvements captured during work. Not active plans — promote items
to `docs/plans/<entry>.md` when ready to act. See `CLAUDE.md` § "Capture, Don't
Pursue, Tangential Optimisations".

---

## Open

### Migrate datasets out of `/run/data_raid5/scratch/`
- **Trigger:** built TIFFs/Zarr live in lorn's scratch convention, which is
  semantically transient. Decided 2026-05-07 to move to
  `/run/data_raid5/shared_data/wrf_wsts/` so the new colleague reads from the
  same place without permission gymnastics.
- **Cost:** ~tens of GB rsync; lockstep update of every script and YAML that
  references the old path. Pair with the de-hardcoding item below since both
  touch the same files.
- **Status:** open — destination chosen, not yet executed.

### De-hardcode the `/run/host/run/data_raid5/...` data paths
- **Trigger:** lorn's preprocessing scripts (`build_all_datasets.sh`,
  `BuildWRFWSTS.py`'s defaults) hardcode the podman-style path. The
  devcontainer bind-mounts `/run/data_raid5` directly, so `postCreate.sh`
  symlinks `/run/host/run/data_raid5 → /run/data_raid5` as a compat shim.
- **Impact:** shim is silent and works, but it's a band-aid. A user on a
  different machine without the shim gets confusing FileNotFoundError.
  Shell scripts now use env-var defaults (`SOURCE_WSTS=...`) — extend that
  to the Python preprocessing entrypoints too.
- **Cost:** ~1h. Add a `DATA_ROOT` env var, thread through CLI args, drop
  the shim from `postCreate.sh`.
- **Status:** open

### Investigate `test_loss = 1.8e+30` from the dry run
- **Trigger:** 2026-05-08 100-epoch dry run produced a wildly inflated
  `test_loss` while classification metrics were normal. Almost certainly
  numerical blow-up in focal loss on a single test batch (NaN inputs from
  WRF features, or degenerate labels).
- **Plan:** add `torch.nan_to_num` / clamp on the loss path, or guard
  `test_step`. Repro: re-run fold 0, dump per-batch losses, find the outlier.
- **Cost:** ~half day debugging.
- **Status:** open — flagged for lorn 2026-05-08.

### Validate `build_all_datasets.sh` end-to-end in the devcontainer
- **Trigger:** ported from distrobox+conda to uv 2026-05-08 but not re-run.
- **Risk:** wrf-python (`uv sync --extra wrf`) build path may need work; WRF
  NetCDF reads might surface env mismatches.
- **Cost:** one full preprocessing run, ~hours.
- **Status:** open — deferred since scratch datasets already exist.

### Persistent wandb auth across container rebuilds
- **Trigger:** `~/.netrc` lives outside the persisted `~/.claude/` mount, so
  `wandb login` has to be redone after every container rebuild.
- **Options:** add `~/.netrc` to the mounts in `devcontainer.json`, or read
  `WANDB_API_KEY` from a host env var.
- **Cost:** five minutes once the right pattern is picked.

### Persistent checkpoint storage
- **Trigger:** `cfgs/trainer_single_gpu.yaml` and `train_wrf_vs_wsts.sh`
  default to `/tmp/lightning_logs`, which dies on container restart.
- **Plan:** default to `/run/data_raid5/<user>/lightning_logs/` or similar.
- **Cost:** small; a path change in one config + one script.

### SSH agent forwarding inside the devcontainer
- **Trigger:** socket forwards correctly but the local agent has no keys
  loaded; `git push` to GitHub is blocked. The postCreate hook prints clear
  guidance.
- **Plan:** verify the laptop side following the postCreate hint; if that
  doesn't work, compare with another working devcontainer setup.
- **Cost:** fiddly, mostly host-config.

### Fix hardcoded `test_pr_curve_data.npz` path in BaseModel
- **Trigger:** `src/models/BaseModel.py:318` calls
  `np.savez("test_pr_curve_data.npz", ...)` with a relative path, so every
  test run overwrites a file in the repo root. The file was historically
  committed; .gitignored 2026-05-08 to stop the pollution.
- **Plan:** write to `os.path.join(self.trainer.default_root_dir, ...)` or
  the active checkpoint dir so the artefact lives next to the run that
  produced it.
- **Cost:** ~10 min including a test run to confirm.
- **Status:** open — gitignore band-aid in place since 2026-05-08.

### Re-enable strict ruff rules across upstream code
- **Trigger:** bumping `target-version` to py312 surfaced ~378 ruff warnings
  in inherited WSTS+ code (UP006/UP045 typing modernisation, W293 trailing
  whitespace, F401 unused imports, etc.). Most are auto-fixable.
- **Plan:** run `uv run ruff check . --fix` + `uv run ruff format .` as a
  single dedicated commit so the diff is reviewable in isolation. Then
  restore `select = ["E", "F", "I", "W", "UP"]` in `pyproject.toml` and
  drop the temporary ignores.
- **Cost:** ~30 min including diff review.
- **Status:** open — narrowed select (`["E", "F"]`) in place since 2026-05-08.

### Drop remaining committed clutter from lorn's cherry-picks
- **Trigger:** lorn's commits include `.nvimlog`, `.codex`, `package.json` /
  `package-lock.json` (Node tooling unrelated to the project), and
  `test_pr_curve_data.npz` (binary test artifact in the tree).
- **Impact:** tree noise; the `.npz` bloats clones.
- **Cost:** ~10 min, one cleanup commit.
- **Status:** open. (`scripts/podman_*.sh` and `run_in_project_env.sh`
  already deleted 2026-05-08.)

### Decide on the `WildfireSpreadTS/` reference checkout
- **Trigger:** the previous stale setup had a sibling clone of slahrichi's
  repo at `WFSTS/WildfireSpreadTS/` for reference. Wiped during setup. May
  or may not be useful to re-add as a gitignored submodule for diffing.
- **Cost:** 5 min if we want it.
- **Status:** open (probably not needed).

---

## Done

- **2026-05-08** — Verify WSTS+ training works under torch 2.6 + pytorch-lightning
  2.5. Dry run completed end-to-end on the WRF-augmented monotemporal config (100
  epochs, fold 0). Three pipeline bugs surfaced and fixed in commit `8db2e69`.
- **2026-05-08** — Deleted lorn's podman+distrobox helper scripts; devcontainer
  is the only supported flow now. Build scripts ported to `uv run`.
- **2026-05-07** — Fix the devcontainer postCreate failure (wrf-python missing
  numpy build dep). Commit `11731ae`.
