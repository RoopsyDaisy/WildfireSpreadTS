#!/usr/bin/env python3
import argparse
from collections import defaultdict
from pathlib import Path
import re

def parse_date_from_filename(name: str):
    # wrfout_d01_YYYY-MM-DD_HH:MM:SS
    m = re.search(r"wrfout_d01_(\d{4}-\d{2}-\d{2})_", name)
    return m.group(1) if m else None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, help="WRF root (e.g., /run/host/run/data_raid5/lornjaeger/trimmed)")
    parser.add_argument("--print_fire_counts", action="store_true", help="Print per-fire counts")
    args = parser.parse_args()

    root = Path(args.root)
    fire_dirs = sorted([p for p in root.iterdir() if p.is_dir() and p.name.startswith("fire_")])
    if not fire_dirs:
        raise RuntimeError(f"No fire_* directories under {root}")

    total_dates = set()
    fire_counts = {}

    for fire_dir in fire_dirs:
        search_root = fire_dir / "wrf"
        if not search_root.exists():
            search_root = fire_dir
        dates = set()
        for path in search_root.rglob("wrfout_d01_*"):
            if ".tmp" in path.name:
                continue
            d = parse_date_from_filename(path.name)
            if d:
                dates.add(d)
                total_dates.add(d)
        fire_counts[fire_dir.name] = len(dates)

    if args.print_fire_counts:
        for fire, count in sorted(fire_counts.items()):
            print(f"{fire}: {count}")

    print(f"Fires: {len(fire_counts)}")
    print(f"Distinct fire-days (sum per fire): {sum(fire_counts.values())}")
    print(f"Distinct dates overall: {len(total_dates)}")


if __name__ == "__main__":
    main()
