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

### Fix sentinel-fill leak in BuildWRFWSTS upstream
- **Trigger:** two fires (`2018/fire_22258421`, `2021/fire_25294687`) have
  NetCDF `_FillValue` (~1e+36) in channels 5 / 17 of the WRF Zarr because
  `BuildWRFWSTS.average_wrf_files` sums files without filtering the fill
  value. Currently mitigated by a load-time clip in the dataloader (see
  `FireSpreadDataset.preprocess_and_augment`, gated on `wrf_data: bool`).
- **Plan:** add a fill-value mask in `BuildWRFWSTS._normalize_wrf_array` or
  in `average_wrf_files`; re-run preprocessing for the affected fires (or
  the whole dataset). Once preprocessing is clean, drop the load-time clip
  band-aid.
- **Cost:** ~30 min for the code change, plus a full preprocessing rerun
  (~hours) if we re-do everything. Or surgical re-run of just the 2 fires.
- **Status:** open. Mitigation in place; upstream fix waiting for the next
  BuildWRFWSTS validation pass.

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

### Delete the 5 dead-end fires from scratch (host-side rm required)
- **Trigger:** 5 fires (`fire_22141572`, `fire_23301395`, `fire_24104628`,
  `fire_24104636`, `fire_25295026`) have only 1 WRF-enriched TIFF each
  because most of their days lacked current+next WRF coverage. They contribute
  zero training samples (need ≥2 days for `n_leading=1`) but emit
  RuntimeWarnings on every dataset prep. Lorn confirmed his "fix" was
  manual deletion he never did.
- **Why host-side:** files are owned by `nobody:nogroup` from the
  devcontainer's userns-mapped perspective. `sudo rm` inside the container
  hits permission denied because the namespace can't elevate to a user
  that owns those files.
- **Plan:** the `sudo bash -c '...'` one-liner from the 2026-05-08 chat
  with safety guards (safe-root check, no-`..`, no-symlink-escape,
  print-each-rm). Total ~54 MB across 20 dirs (5 fires × 4 storage roots:
  `wrf_wsts/`, `wrf_wsts_match/`, `wrf_wsts_zarr/`, `wrf_wsts_zarr_match/`).
- **Cost:** 30 seconds once on the host shell.
- **Status:** open — Rupert deferred 2026-05-08.

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

- **2026-05-13** — Resolved SSH agent forwarding for the devcontainer.
  VS Code's auto-injected proxy socket is broken on this host, but the
  bind-mounted `/ssh-agent` works. `postCreate.sh` now installs a
  `/etc/profile.d/01-ssh-agent.sh` override that pins `SSH_AUTH_SOCK=/ssh-agent`
  for new shells (login + interactive non-login). Commit `4d6683f`.
- **2026-05-10** — Resolved `test_loss = 1.8e+30` anomaly. Two parts: (a)
  recomputed standardization stats over the actual WRF data (new
  `src/dataloader/wrf_stats.py` + `scripts/compute_wrf_stats.py`); (b)
  added a load-time clip for NetCDF sentinel-fill values that leak into
  ch 5 / 17 for two fires. Gated behind `wrf_data: bool` on the data
  config so the matched-WSTS run is unaffected. test_loss now 0.00364,
  test_AP unchanged (0.527 vs 0.522). Commit `498e9d9`.
- **2026-05-10** — Persistent checkpoint storage. `train_wrf_vs_wsts.sh`
  default OUT_DIR now `/run/data_raid5/scratch/lightning_logs`
  (env-var overridable), survives container restarts. Commit `498e9d9`.
- **2026-05-08** — Audited lorn's three open questions: channel mapping
  verified (coherent GRIDMET/GFS → WRF replacement strategy), 5 dead-end
  fires identified for cleanup (deferred to host shell), test_loss anomaly
  partially diagnosed (raw inputs clean, stale stats found as adjacent bug).
- **2026-05-08** — Verify WSTS+ training works under torch 2.6 + pytorch-lightning
  2.5. Dry run completed end-to-end on the WRF-augmented monotemporal config (100
  epochs, fold 0). Three pipeline bugs surfaced and fixed in commit `8db2e69`.
- **2026-05-08** — Deleted lorn's podman+distrobox helper scripts; devcontainer
  is the only supported flow now. Build scripts ported to `uv run`. Commit `07bc189`.
- **2026-05-07** — Fix the devcontainer postCreate failure (wrf-python missing
  numpy build dep). Commit `11731ae`.
