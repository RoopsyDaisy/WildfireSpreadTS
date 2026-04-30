from pathlib import Path

import numpy as np
import rasterio


def get_years(data_dir: str):
    years = sorted([int(p.name) for p in Path(data_dir).iterdir()
                    if p.is_dir() and p.name.isdigit()])
    if not years:
        raise RuntimeError(f"No year directories found in {data_dir}")
    return years


def iter_fire_stacks(data_dir: str):
    for year in get_years(data_dir):
        year_dir = Path(data_dir) / str(year)
        fire_dirs = sorted([p for p in year_dir.iterdir() if p.is_dir()])
        for fire_dir in fire_dirs:
            img_files = sorted(fire_dir.glob("*.tif"))
            if not img_files:
                continue

            imgs = []
            lnglat = None
            img_dates = []
            for img_path in img_files:
                with rasterio.open(img_path, "r") as ds:
                    imgs.append(ds.read())
                    if lnglat is None:
                        lnglat = ds.lnglat()
                img_dates.append(img_path.name.split("_")[0].replace(".tif", ""))

            x = np.stack(imgs, axis=0)
            x[:, -1, ...] = np.nan_to_num(x[:, -1, ...], nan=0)
            x[:, -1, ...] = np.floor_divide(x[:, -1, ...], 100)

            yield year, fire_dir.name, img_dates, lnglat, x
