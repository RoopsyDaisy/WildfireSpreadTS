# Backlog

Tangential improvements captured during work. Not active plans — promote items
to `docs/plans/<entry>.md` when ready to act. See `CLAUDE.md` § "Capture, Don't
Pursue, Tangential Optimisations".

---

## Open

### De-hardcode the `/run/host/run/data_raid5/...` data paths
- **Trigger**: Lorn's preprocessing scripts (`scripts/build_all_datasets.sh`,
  `scripts/train_wrf_vs_wsts.sh`, paths inside `BuildWRFWSTS.py`) hardcode the
  podman-style path `/run/host/run/data_raid5/...`. The devcontainer
  bind-mounts `/run/data_raid5` directly, so `postCreate.sh` symlinks
  `/run/host/run/data_raid5 → /run/data_raid5` as a compatibility shim.
- **Impact**: Shim is silent and works, but it's a band-aid. A user running
  these scripts on a different machine (no `/run/host` namespace) without the
  shim will get confusing FileNotFoundError. New contributors won't understand
  why the path looks the way it does.
- **Cost**: ~1h. Add a `DATA_ROOT` env var (default `/run/data_raid5`),
  thread through shell scripts and the BuildWRFWSTS.py CLI, drop the shim.
- **Status**: open

### Drop committed clutter from cherry-picked commits
- **Trigger**: Lorn's commits include `.nvimlog`, `.codex`, `package.json` /
  `package-lock.json` (Node tooling unrelated to the project), `test_pr_curve_data.npz`
  (binary test artifact), and `scripts/podman_*.sh` (we use devcontainers).
- **Impact**: Tree noise; binary `.npz` bloats clones; podman scripts may
  confuse new contributors looking for the canonical run path.
- **Cost**: ~10 min. One cleanup commit. Worth doing before the project
  attracts collaborators.
- **Status**: open

### Decide on the `WildfireSpreadTS/` reference checkout
- **Trigger**: The previous stale setup had a sibling clone of slahrichi's
  repo at `WFSTS/WildfireSpreadTS/` for reference. Wiped during setup. May or
  may not be useful to re-add as a gitignored submodule for diffing against
  upstream.
- **Impact**: Easier upstream-tracking vs more clutter. Currently we just
  `git remote add slahrichi ...` and `git fetch` when needed.
- **Cost**: 5 min if we want it.
- **Status**: open (probably not needed)

### Verify WSTS+ training still works under torch 2.5
- **Trigger**: Pinned dependencies were bumped (torch 2.0 → 2.5+, pytorch-lightning
  2.0 → 2.4+, numpy 1.22 → 1.26+) during initial setup. Two years of API churn
  may have broken training/eval paths in `src/`.
- **Impact**: If broken, blocks all training experiments. Highest-priority
  item once devcontainer is up.
- **Cost**: Could be 30 min (deprecation-warning fixes) to a few hours
  (Lightning lifecycle changes). Hard to estimate until tried.
- **Status**: open — first thing to do after first container build

---

## Done

(none yet)
