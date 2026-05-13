"""Compute per-channel mean / std / missing-value rate over the WRF-enriched
Zarr dataset. Streaming, to avoid loading 6.8 GB at once.

Output goes to stdout in a copy-pasteable form for pasting into
src/dataloader/wrf_stats.py.

Usage:
    PYTHONPATH=$PWD:$PWD/src uv run python scripts/compute_wrf_stats.py \\
        --data_dir /run/data_raid5/scratch/wrf_wsts_zarr \\
        --years 2018 2019 2020 2021
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import numpy as np
import zarr


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data_dir", required=True, type=Path)
    parser.add_argument("--years", required=True, type=int, nargs="+")
    parser.add_argument("--n_channels", type=int, default=23)
    parser.add_argument(
        "--sentinel_threshold",
        type=float,
        default=1e10,
        help=(
            "Treat |value| > threshold as NetCDF fill / sentinel (counts toward "
            "missing_values rate, excluded from mean/std). WRF NetCDFs leak ~1e+36 "
            "fill values for some pixels; default 1e10 catches them with margin."
        ),
    )
    args = parser.parse_args()

    n_ch = args.n_channels
    sum_v = np.zeros(n_ch, dtype=np.float64)
    sum_sq = np.zeros(n_ch, dtype=np.float64)
    n_finite = np.zeros(n_ch, dtype=np.int64)
    n_total = np.zeros(n_ch, dtype=np.int64)

    n_fires = 0
    n_days_total = 0
    for year in args.years:
        year_dir = args.data_dir / str(year)
        fire_zarrs = sorted(year_dir.glob("*.zarr"))
        print(f"Year {year}: {len(fire_zarrs)} fires")
        for fz in fire_zarrs:
            try:
                root = zarr.open_group(str(fz), mode="r")
                data = np.asarray(root["data"])  # (n_days, n_ch, H, W)
            except Exception as exc:
                print(f"  skip {fz.name}: {exc}")
                continue

            n_fires += 1
            n_days_total += data.shape[0]

            for c in range(n_ch):
                flat = data[:, c, :, :].astype(np.float64).ravel()
                # "Valid" = finite AND not a sentinel-fill (|value| > threshold).
                valid_mask = np.isfinite(flat) & (np.abs(flat) <= args.sentinel_threshold)
                vals = flat[valid_mask]
                sum_v[c] += vals.sum()
                sum_sq[c] += np.square(vals).sum()
                n_finite[c] += vals.size
                n_total[c] += flat.size

    print(f"\nTotals: {n_fires} fires, {n_days_total} fire-days")
    print(f"Pixels per channel: {n_total[0]:,}")

    mean = sum_v / np.maximum(n_finite, 1)
    var = (sum_sq / np.maximum(n_finite, 1)) - np.square(mean)
    var = np.maximum(var, 0.0)
    std = np.sqrt(var)
    missing_rate = 1.0 - (n_finite / np.maximum(n_total, 1))

    def fmt(arr: np.ndarray, label: str) -> str:
        lines = [f'        "{label}": np.array(']
        lines.append("            [")
        for i, v in enumerate(arr):
            comma = "," if i < len(arr) - 1 else ""
            lines.append(f"                {float(v):.16g}{comma}  # ch{i}")
        lines.append("            ],")
        lines.append("            dtype=np.float32,")
        lines.append("        ),")
        return "\n".join(lines)

    years_tuple = tuple(args.years)
    print()
    print("=" * 64)
    print("Paste the block below into src/dataloader/wrf_stats.py")
    print("=" * 64)
    print()
    print("WRF_STATS = {")
    print(f"    {years_tuple}: {{")
    print(fmt(mean.astype(np.float32), "means"))
    print(fmt(std.astype(np.float32), "stds"))
    print(fmt(missing_rate.astype(np.float32), "missing_values"))
    print("    },")
    print("}")


if __name__ == "__main__":
    main()
