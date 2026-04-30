import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from tqdm import tqdm


def build_matched_wsts(source_wsts: Path, reference_wrf: Path, out_dir: Path, copy_files: bool):
    ref_files = list(reference_wrf.rglob("*.tif"))
    if not ref_files:
        raise RuntimeError(f"No TIFFs found under {reference_wrf}")

    total = 0
    written = 0
    missing = 0

    for ref_path in tqdm(ref_files, desc="Matching TIFFs"):
        rel = ref_path.relative_to(reference_wrf)
        src_path = source_wsts / rel
        dst_path = out_dir / rel
        total += 1

        if not src_path.exists():
            missing += 1
            continue

        if dst_path.exists():
            continue

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        if copy_files:
            shutil.copy2(src_path, dst_path)
        else:
            os.symlink(src_path, dst_path)
        written += 1

    print(f"Done. Reference files: {total}, written: {written}, missing in source: {missing}.")


def run_hdf5_build(matched_dir: Path, hdf5_dir: Path):
    cmd = [
        sys.executable,
        "src/preprocess/CreateHDF5Dataset.py",
        "--data_dir",
        str(matched_dir),
        "--target_dir",
        str(hdf5_dir),
    ]
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd)


def run_zarr_build(matched_dir: Path, zarr_dir: Path):
    cmd = [
        sys.executable,
        "src/preprocess/CreateZarrDataset.py",
        "--data_dir",
        str(matched_dir),
        "--target_dir",
        str(zarr_dir),
    ]
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd)


def normalize_host_path(path_str: str) -> Path:
    path = Path(path_str)
    if path.exists():
        return path
    if "/run/hosts/" in path_str:
        alt = Path(path_str.replace("/run/hosts/", "/run/host/"))
        if alt.exists():
            return alt
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source_wsts",
        type=str,
        default="/run/host/run/data_raid5/shared_data/WSTS",
        help="Path to original WSTS directory (years/...)",
    )
    parser.add_argument(
        "--reference_wrf",
        type=str,
        default="/run/host/run/data_raid5/scratch/wrf_wsts",
        help="Path to wrf_wsts directory (reference list of days)",
    )
    parser.add_argument(
        "--out_dir",
        type=str,
        default="/run/host/run/data_raid5/scratch/wrf_wsts_match",
        help="Output directory for matched WSTS (copied)",
    )
    parser.add_argument(
        "--hdf5_dir",
        type=str,
        default="/run/host/run/data_raid5/scratch/wrf_wsts_hdf5_match",
        help="Output directory for matched HDF5 (optional if --make_hdf5)",
    )
    parser.add_argument(
        "--zarr_dir",
        type=str,
        default="/run/host/run/data_raid5/scratch/wrf_wsts_zarr_match",
        help="Output directory for matched Zarr (optional if --make_zarr)",
    )
    parser.add_argument(
        "--symlink",
        action="store_true",
        help="Use symlinks instead of copying",
    )
    parser.add_argument(
        "--make_hdf5",
        action="store_true",
        help="Build HDF5 files after matching",
    )
    parser.add_argument(
        "--make_zarr",
        action="store_true",
        help="Build Zarr stores after matching",
    )
    args = parser.parse_args()

    source_wsts = normalize_host_path(args.source_wsts)
    reference_wrf = normalize_host_path(args.reference_wrf)
    out_dir = normalize_host_path(args.out_dir)
    hdf5_dir = normalize_host_path(args.hdf5_dir)
    zarr_dir = normalize_host_path(args.zarr_dir)

    build_matched_wsts(
        source_wsts,
        reference_wrf,
        out_dir,
        copy_files=not args.symlink,
    )

    if args.make_hdf5:
        run_hdf5_build(out_dir, hdf5_dir)
    if args.make_zarr:
        run_zarr_build(out_dir, zarr_dir)


if __name__ == "__main__":
    main()
