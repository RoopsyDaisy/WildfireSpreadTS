import argparse
import shutil
import sys
from pathlib import Path

from tqdm import tqdm

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.preprocess.storage_build_utils import get_years, iter_fire_stacks

try:
    import zarr
except ImportError as exc:
    raise ImportError("zarr is required to run CreateZarrDataset.py") from exc


parser = argparse.ArgumentParser()
parser.add_argument("--data_dir", type=str,
                    help="Path to dataset directory", required=True)
parser.add_argument("--target_dir", type=str,
                    help="Path to directory where the Zarr stores should be stored", required=True)
parser.add_argument("--skip_existing", action="store_true",
                    help="Skip stores that already exist instead of overwriting.")
args = parser.parse_args()

years = get_years(args.data_dir)

for y in years:
    Path(args.target_dir, str(y)).mkdir(parents=True, exist_ok=True)

for year, fire_name, img_dates, lnglat, imgs in tqdm(iter_fire_stacks(args.data_dir)):
    zarr_path = Path(args.target_dir) / str(year) / f"{fire_name}.zarr"

    if zarr_path.exists() and args.skip_existing:
        print(f"Store {zarr_path} already exists, skipping...")
        continue
    elif zarr_path.exists():
        print(f"Store {zarr_path} already exists, overwriting...")
        shutil.rmtree(zarr_path)

    root = zarr.open_group(str(zarr_path), mode="w")
    dset = root.create_dataset(
        "data",
        data=imgs,
        shape=imgs.shape,
        chunks=(1,) + imgs.shape[1:],
        dtype=imgs.dtype,
    )
    dset.attrs["year"] = int(year)
    dset.attrs["fire_name"] = fire_name
    dset.attrs["img_dates"] = [str(img_date) for img_date in img_dates]
    if lnglat is None:
        dset.attrs["lnglat"] = None
    else:
        dset.attrs["lnglat"] = [float(lnglat[0]), float(lnglat[1])]
