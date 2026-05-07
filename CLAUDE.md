# WRF Wildfire Spread Prediction

## Project Overview

Extends the [WildfireSpreadTS (WSTS+)](https://github.com/slahrichi/WildfireSpreadTS) deep-learning fire-spread benchmark with **WRF (Weather Research and Forecasting) simulation outputs as additional input features**. The hypothesis: numerical-weather features computed over the duration of a fire (T2, RAINC+RAINCC, U10/V10, Q2) improve next-day spread prediction over satellite-only baselines.

This repo is one prong of a wider PhD research programme on the **evolution of wildfires**. Downstream, fire-evolution dynamics inferred here are intended to feed back into burn-probability work (predicting probability of *fast-moving or intense* fire, not just any fire).

Upstream lineage: SebastianGer → slahrichi (WSTS+ paper) → forked here, plus cherry-picked WRF integration scaffolding from lorn-jaeger (`BuildWRFWSTS.py`, training scripts, monotemporal WRF config).

### Current state
- WSTS+ baseline (UNet / SegFormer / UTAE / Swin) intact under `src/`
- WRF dataset builder at `src/preprocess/BuildWRFWSTS.py` (lorn) — reads WRF NetCDFs, regrids to WSTS TIFF grid, writes enriched TIFFs
- Zarr conversion at `src/preprocess/CreateZarrDataset.py`
- WRF training config at `cfgs/data_monotemporal_wrf_full_features.yaml`
- Pipeline scripts under `scripts/` (`build_all_datasets.sh`, `train_wrf_vs_wsts.sh`)
- See `RUN_TRAINING_NOTES.md` and `AGENT.md` for lorn's prior context

### Mode Selection
Single mode for now — coding/research. Slash commands (`/code`, `/wrap`) provide narrow context loading. New modes can be added under `.claude/commands/` as the project grows.

---

## Working Principles

These apply across all work in this repo.

### Discover Before Propose
- **Search for existing similar work** before proposing new work
- Check relevant directories, README files, indices, status files
- Never be "surprised" by prior work — if you didn't look, that's a failure
- If there might be prior experiments, approaches, or decisions, **look for them or ask**
- Don't assume a directory is empty or a problem is novel

### Verify Before Create
- **Inspect the target location** before creating files
- `ls` the directory, read 1-2 similar files to match conventions
- Understand the structure before adding to it
- If uncertain about placement or format, **ask**

### Persist Important State Early
- For conversations involving plans, decisions, requirements → **write to files**, not just chat
- Don't rely on chat memory for anything that should survive context limits
- Write intermediate status (STATUS.md, notes) not just final outputs
- When user explicitly rejects an approach, treat as **hard constraint** — don't re-raise it

### Ask Don't Assume
- If unsure about conventions, standards, or existing work → ask
- Better to ask a clarifying question than make a wrong assumption
- Especially for structural decisions (where to put files, what format, what's been tried)

### Productive Disagreement
- **Quality of challenges matters** — a good challenge brings new information or a different perspective
- A bad challenge repeats the same argument hoping for a different answer
- If re-raising a previously rejected point, ask yourself: "What's new here?" If nothing, move on
- **Trust stated problem magnitudes** — user says "50% bias" → work with that, don't counter with theoretical expectations
- **After rejection:** accept as working constraint; only revisit with genuinely new information
- When revisiting: explicitly flag it ("I know you rejected X, but [new angle]. Worth reconsidering?")

### Capture, Don't Pursue, Tangential Optimisations
- During work you'll spot things — perf wins, structural improvements, library bumps, storage-strategy ideas — that are NOT the current task. The default is: **add an entry to `docs/BACKLOG.md` and keep going.**
- **Trivial fixes are exempt:** if you can finish it in <5 minutes with no separate testing or scope expansion (typo, missing comment, obvious one-line cleanup, dead-import removal next to code you're already editing), just do it inline and mention it in passing. The bar: would mentioning it in the commit body feel forced? If yes, it's trivial enough to fold in. If you'd want a separate commit, it's BACKLOG-worthy.
- **Band-aids are never trivial:** when you write a workaround (forced-synchronous scheduler, hardcoded scratch path, disabled compression, skip-if-broken guard), add a BACKLOG entry naming the proper fix and link the band-aid's inline comment to that entry. The whole point of "band-aid" is "the proper fix isn't trivial."
- Bar to entry: title, trigger, rough impact, rough cost, status. Three sentences max unless there's reason to expand. Don't gate on certainty — it's a backlog, not a plan.
- When something is ready to act on, promote to `docs/plans/<entry>.md` and link back. When it ships, move to `## Done` or remove.

### Git Commit Messages
- **No authorship or attribution in git commit messages.** Do not add `Co-Authored-By`, `Signed-off-by`, or any other trailer that attributes the commit to an AI assistant, a model, or Anthropic. The commit author metadata already records who made the commit; the message should describe the change, not its source.

---

## Workflow Patterns

### Plan Before Acting
For non-trivial changes, outline the plan first:
1. List files to create/modify
2. Describe what each change does
3. Identify assumptions
4. Get approval before writing code

### When Stuck (The Loop)
If repeating ineffective fixes or going in circles:
1. Stop and summarize what's been tried
2. Ask to start fresh with a clear problem statement
3. Consider if the approach itself is wrong

### Code Review
When asked to review a PR, branch, or commit range:
1. Read the diff in full before forming opinions
2. Separate "must fix" (correctness, safety) from "nice to have" (style, minor refactor)
3. Give findings to the user; do not post to GitHub directly unless explicitly told to

### Large / Multi-Phase Changes
For work spanning many files, new subsystems, or multiple logical phases (refactors, new features with plan docs in `docs/plans/`):

1. **Land each phase as its own PR.** Target ≤500 lines changed per PR so it's reviewable in one sitting. PRs above this size degrade review quality regardless of reviewer.
2. **Architecture/design docs land first as doc-only PRs** for explicit sign-off before any implementation code. Prevents "design emerged from the code" drift.
3. **The first code PR should include a baseline-equivalence test** demonstrating no behaviour change on existing code paths. Every subsequent PR should keep that test green.
4. **PR description references the plan doc and names the phase** this PR implements. Reviewers need the context; they don't carry it across PRs.
5. **Keep refactor-only commits separate from feature commits.** A PR that both moves code around and adds behaviour is harder to review than two PRs doing each.
6. **Open as draft early.** Pushes to a draft PR are visible to reviewers without requesting review; move to ready-for-review at phase completion.

---

## Coding Mode

### Project Structure
- `src/dataloader/` — `FireSpreadDataset.py`, `FireSpreadDataModule.py` (PyTorch Lightning)
- `src/models/` — model architectures (UNet, SegFormer, UTAE, Swin)
- `src/preprocess/` — dataset construction
  - `BuildWRFWSTS.py` — main WRF→TIFF enrichment (lorn)
  - `BuildMatchedWSTS.py` — matched-only WSTS subset
  - `CreateHDF5Dataset.py`, `CreateZarrDataset.py` — array format converters
- `src/train.py` — training entrypoint
- `cfgs/` — YAML configs for data + model variants (jsonargparse)
- `scripts/` — shell pipeline drivers (dataset build, training)
- `docs/` — technical docs and plans (create `docs/BACKLOG.md` on first entry)
- `WildfireSpreadTS/` (if present) — original repo as a reference checkout (gitignored)

### Tech Stack
- **Package management**: `uv` with `uv.lock` and `pyproject.toml`
- **Python**: 3.10 (matches WSTS+ tested environment)
- **PyTorch**: 2.5+ on CUDA 12.4 (modernised from WSTS+'s pinned 2.0). Wheels pulled from `https://download.pytorch.org/whl/cu124` via `[tool.uv.sources]`.
- **Training framework**: PyTorch Lightning 2.4+, Weights & Biases for tracking
- **Geospatial**: rasterio, xarray, geopandas, pyproj, netcdf4
- **WRF I/O**: netcdf4 directly; `wrf-python` is an optional extra (`uv sync --extra wrf`) — `BuildWRFWSTS.py` guards the import
- **Storage**: Zarr is preferred over HDF5 for new datasets (lorn's call, see `RUN_TRAINING_NOTES.md`)

### Code Style
- **Formatting**: ruff (line-length 99, py310 target, config in pyproject.toml)
- **Type hints**: Preferred (add to new code, don't retrofit blindly)
- **Docstrings**: Google style
- **Run linter**: `uv run ruff check .` and `uv run ruff format .`

### Key Commands
```bash
# Sync env (auto on container create/start)
uv sync

# With optional WRF reader
uv sync --extra wrf

# Lint + format
uv run ruff check .
uv run ruff format .

# Build the WRF-enriched dataset (lorn's pipeline; data paths hardcoded)
./scripts/build_all_datasets.sh --workers 8

# Train (WANDB_MODE=disabled to skip wandb auth in dev)
WANDB_MODE=disabled ./scripts/train_wrf_vs_wsts.sh --fold 0 --epochs 50 --batch 32 --workers 16

# Quick GPU sanity check
uv run python -c "import torch; print(torch.cuda.is_available(), torch.cuda.device_count())"
```

### Data Paths
Lorn's preprocessing scripts hardcode `/run/host/run/data_raid5/...` (a podman-mount convention). The devcontainer mounts `/run/data_raid5` directly and `postCreate.sh` symlinks `/run/host/run/data_raid5 → /run/data_raid5` so existing scripts work unmodified. **De-hardcoding these paths is a BACKLOG item** — see `docs/BACKLOG.md`.

Canonical paths inside the container:
- `/run/data_raid5/shared_data/WSTS` — WSTS source TIFFs
- `/run/data_raid5/lornjaeger/trimmed` — WRF NetCDF inputs (rsync target going forward)
- `/run/data_raid5/scratch/wrf_wsts` — enriched TIFF outputs
- `/run/data_raid5/scratch/wrf_wsts_zarr` — Zarr training inputs

### Conventions Inherited from WSTS+ to Watch
- `jsonargparse[signatures]` is used for CLI/config wiring throughout — adding new model or dataloader args usually means a YAML edit, not argparse boilerplate
- `pytorch-lightning` 2.x lifecycle: keep training step / val step / configure_optimizers idiomatic
- The `cfgs/` YAMLs use `class_path` references — moving a class breaks every config that references it
