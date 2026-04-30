import argparse
import os
import sys
from pathlib import Path

import h5py
from tqdm import tqdm

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.preprocess.storage_build_utils import get_years, iter_fire_stacks


parser = argparse.ArgumentParser()
parser.add_argument("--data_dir", type=str,
                    help="Path to dataset directory", required=True)
parser.add_argument("--target_dir", type=str,
                    help="Path to directory where the HDF5 files should be stored", required=True)
parser.add_argument("--skip_existing", action="store_true",
                    help="Skip files that already exist instead of overwriting.")
args = parser.parse_args()

# Need to prevent some error with HDF5 files being locked and thereby inaccessible
os.environ["HDF5_USE_FILE_LOCKING"] = "FALSE"

years = get_years(args.data_dir)

for y in years:
    Path(args.target_dir, str(y)).mkdir(parents=True, exist_ok=True)

for year, fire_name, img_dates, lnglat, imgs in tqdm(iter_fire_stacks(args.data_dir)):
    h5_path = Path(args.target_dir) / str(year) / f"{fire_name}.hdf5"

    if h5_path.is_file() and args.skip_existing:
        print(f"File {h5_path} already exists, skipping...")
        continue
    elif h5_path.is_file():
        print(f"File {h5_path} already exists, overwriting...")

    with h5py.File(h5_path, "w") as f:
        dset = f.create_dataset("data", imgs.shape, data=imgs)
        dset.attrs["year"] = year
        dset.attrs["fire_name"] = fire_name
        dset.attrs["img_dates"] = img_dates
        dset.attrs["lnglat"] = lnglat
