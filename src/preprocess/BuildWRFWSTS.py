import argparse
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
import os
import concurrent.futures

import numpy as np

try:
    import rasterio
except ImportError as exc:
    raise ImportError("rasterio is required to run BuildWRFWSTS.py") from exc

try:
    import xarray as xr
except ImportError as exc:
    raise ImportError("xarray is required to run BuildWRFWSTS.py") from exc
try:
    from pyproj import Transformer
except ImportError as exc:
    raise ImportError("pyproj is required to run BuildWRFWSTS.py") from exc
try:
    from scipy.spatial import cKDTree
except ImportError as exc:
    raise ImportError("scipy is required to run BuildWRFWSTS.py") from exc
try:
    from netCDF4 import Dataset as NetCDFDataset
    import wrf
    HAS_WRF_PY = True
except Exception:
    NetCDFDataset = None
    HAS_WRF_PY = False


WRF_VARS = {
    "t2": "T2",
    "q2": "Q2",
    "u10": "U10",
    "v10": "V10",
    "rainc": "RAINC",
    "rainnc_candidates": ["RAINCC", "RAINNC"],
}


def parse_wrf_date(path: Path) -> str:
    name = path.name
    # Expected: wrfout_d01_YYYY-MM-DD_HH:MM:SS
    parts = name.split("_")
    if len(parts) < 4:
        raise ValueError(f"Unexpected WRF filename: {name}")
    return parts[2]


def index_wrf_files(fire_wrf_dir: Path) -> dict:
    search_root = fire_wrf_dir / "wrf"
    if not search_root.exists():
        search_root = fire_wrf_dir

    wrf_files = []
    for path in search_root.rglob("wrfout_d01_*"):
        name = path.name
        if ".tmp" in name or name.endswith(".tmp"):
            continue
        wrf_files.append(path)
    wrf_by_date = defaultdict(list)
    for wrf_path in wrf_files:
        try:
            date_str = parse_wrf_date(wrf_path)
        except ValueError:
            continue
        wrf_by_date[date_str].append(wrf_path)
    for date_str in wrf_by_date:
        wrf_by_date[date_str].sort()
    return wrf_by_date


def _normalize_wrf_array(arr, name):
    arr = np.asarray(arr)
    if arr.size == 0:
        return None
    if arr.ndim == 3:
        if arr.shape[0] == 0:
            return None
        arr = arr[0]
    elif arr.ndim == 2:
        pass
    else:
        arr = np.squeeze(arr)
        if arr.size == 0:
            return None
        if arr.ndim == 3:
            if arr.shape[0] == 0:
                return None
            arr = arr[0]
    if arr.ndim != 2:
        raise ValueError(f"Unexpected WRF array shape for {name}: {arr.shape}")
    return arr


def _read_wrfpy_var(nc, name):
    arr = None
    try:
        arr = wrf.getvar(nc, name, timeidx=0)
    except Exception:
        pass
    if arr is None and name in nc.variables:
        arr = nc.variables[name][:]
    if arr is None:
        return None
    return _normalize_wrf_array(arr, name)


def _read_var(ds, name):
    if name not in ds:
        raise KeyError(f"WRF variable {name} not found.")
    arr = _normalize_wrf_array(ds[name], name)
    return arr


def _read_rain(ds):
    rainc = _read_var(ds, WRF_VARS["rainc"])
    if rainc is None:
        return None
    rainnc = None
    for cand in WRF_VARS["rainnc_candidates"]:
        if cand in ds:
            rainnc = _normalize_wrf_array(ds[cand], cand)
            break
    if rainnc is None:
        raise KeyError(
            f"None of {WRF_VARS['rainnc_candidates']} found for non-convective rain."
        )
    return rainc + rainnc


def _available_xarray_engines():
    try:
        import xarray as _xr
        return set(_xr.backends.list_engines().keys())
    except Exception:
        return set()


def open_wrf_dataset(path: Path, engine: str | None = None):
    try:
        if engine is None:
            return xr.open_dataset(path, decode_times=False)
        return xr.open_dataset(path, decode_times=False, engine=engine)
    except Exception as exc:
        raise exc


def read_wrf_vars(path: Path):
    if HAS_WRF_PY and NetCDFDataset is not None:
        nc = NetCDFDataset(path)
        try:
            t2 = _read_wrfpy_var(nc, WRF_VARS["t2"])
            q2 = _read_wrfpy_var(nc, WRF_VARS["q2"])
            u10 = _read_wrfpy_var(nc, WRF_VARS["u10"])
            v10 = _read_wrfpy_var(nc, WRF_VARS["v10"])
            rainc = _read_wrfpy_var(nc, WRF_VARS["rainc"])
            raincc = _read_wrfpy_var(nc, "RAINCC")
            rainnc = _read_wrfpy_var(nc, "RAINNC")
            if rainc is None:
                raise RuntimeError("Missing RAINC.")
            if raincc is None and rainnc is None:
                raise RuntimeError("Missing RAINCC/RAINNC.")
            rain = rainc + (raincc if raincc is not None else rainnc)
            if any(v is None for v in (t2, q2, u10, v10, rain)):
                raise RuntimeError("One or more required WRF variables empty.")
            return {"t2": t2, "q2": q2, "u10": u10, "v10": v10, "rain": rain}
        finally:
            nc.close()

    engines = [None]
    available = _available_xarray_engines()
    for eng in ("netcdf4", "h5netcdf"):
        if eng in available:
            engines.append(eng)
    last_exc = None
    for engine in engines:
        try:
            with open_wrf_dataset(path, engine=engine) as ds:
                t2 = _read_var(ds, WRF_VARS["t2"])
                q2 = _read_var(ds, WRF_VARS["q2"])
                u10 = _read_var(ds, WRF_VARS["u10"])
                v10 = _read_var(ds, WRF_VARS["v10"])
                rain = _read_rain(ds)
            if any(v is None for v in (t2, q2, u10, v10, rain)):
                last_exc = ValueError("empty arrays")
                continue
            return {"t2": t2, "q2": q2, "u10": u10, "v10": v10, "rain": rain}
        except Exception as exc:
            last_exc = exc
            continue

    raise RuntimeError(f"Failed reading WRF variables from {path}: {last_exc}")


def read_wrf_coords(path: Path):
    if HAS_WRF_PY and NetCDFDataset is not None:
        nc = NetCDFDataset(path)
        try:
            wrf_lat = _read_wrfpy_var(nc, "XLAT")
            wrf_lon = _read_wrfpy_var(nc, "XLONG")
            if wrf_lat is None or wrf_lon is None:
                raise RuntimeError("Empty XLAT/XLONG arrays.")
            return wrf_lat, wrf_lon
        finally:
            nc.close()

    engines = [None]
    available = _available_xarray_engines()
    for eng in ("netcdf4", "h5netcdf"):
        if eng in available:
            engines.append(eng)
    last_exc = None
    for engine in engines:
        try:
            with open_wrf_dataset(path, engine=engine) as ds:
                if "XLAT" not in ds or "XLONG" not in ds:
                    raise KeyError("WRF dataset missing XLAT/XLONG for reprojection.")
                wrf_lat = _normalize_wrf_array(ds["XLAT"], "XLAT")
                wrf_lon = _normalize_wrf_array(ds["XLONG"], "XLONG")
            if wrf_lat is None or wrf_lon is None:
                last_exc = ValueError("empty XLAT/XLONG arrays")
                continue
            return wrf_lat, wrf_lon
        except Exception as exc:
            last_exc = exc
            continue
    raise RuntimeError(f"Failed reading WRF coords from {path}: {last_exc}")


def average_wrf_files(file_paths):
    sums = {}
    count = 0
    t2_min = None
    t2_max = None
    for path in file_paths:
        try:
            vars_out = read_wrf_vars(path)
        except Exception as exc:
            print(f"Skipping WRF file {path}: {exc}")
            continue

        t2 = vars_out["t2"]
        q2 = vars_out["q2"]
        u10 = vars_out["u10"]
        v10 = vars_out["v10"]
        rain = vars_out["rain"]

        if not sums:
            sums = {
                "t2": np.zeros_like(t2, dtype=np.float64),
                "q2": np.zeros_like(q2, dtype=np.float64),
                "u10": np.zeros_like(u10, dtype=np.float64),
                "v10": np.zeros_like(v10, dtype=np.float64),
                "rain": np.zeros_like(rain, dtype=np.float64),
            }
            t2_min = t2.astype(np.float64, copy=True)
            t2_max = t2.astype(np.float64, copy=True)

        sums["t2"] += t2
        sums["q2"] += q2
        sums["u10"] += u10
        sums["v10"] += v10
        sums["rain"] += rain
        t2_min = np.minimum(t2_min, t2)
        t2_max = np.maximum(t2_max, t2)
        count += 1

    if count == 0:
        raise ValueError("No WRF files provided for averaging.")

    avg = {k: v / count for k, v in sums.items()}
    avg["t2_min"] = t2_min
    avg["t2_max"] = t2_max
    return avg


def wind_speed_and_dir(u10, v10):
    speed = np.sqrt(u10 ** 2 + v10 ** 2)
    # Meteorological wind direction (degrees, direction wind is coming from)
    direction = (np.degrees(np.arctan2(-u10, -v10)) + 360) % 360
    return speed, direction


class WRFResampler:
    def __init__(self, target_crs, target_transform, width, height, wrf_lat, wrf_lon):
        if target_crs is None:
            raise ValueError("Target CRS is missing; cannot resample WRF data.")

        self.width = width
        self.height = height
        self.target_transform = target_transform
        self.target_crs = target_crs

        transformer = Transformer.from_crs("EPSG:4326", target_crs, always_xy=True)
        x_wrf, y_wrf = transformer.transform(wrf_lon, wrf_lat)
        x_wrf = np.asarray(x_wrf)
        y_wrf = np.asarray(y_wrf)

        points = np.column_stack([x_wrf.ravel(), y_wrf.ravel()])
        valid_mask = np.isfinite(points).all(axis=1)
        if not np.any(valid_mask):
            raise ValueError("No valid WRF coordinate points after projection.")

        self.valid_mask = valid_mask
        self.points = points[valid_mask]
        self.minx = np.nanmin(self.points[:, 0])
        self.maxx = np.nanmax(self.points[:, 0])
        self.miny = np.nanmin(self.points[:, 1])
        self.maxy = np.nanmax(self.points[:, 1])

        rows, cols = np.meshgrid(np.arange(height), np.arange(width), indexing="ij")
        xs, ys = rasterio.transform.xy(target_transform, rows, cols, offset="center")
        self.target_x = np.asarray(xs)
        self.target_y = np.asarray(ys)
        target_points = np.column_stack([self.target_x.ravel(), self.target_y.ravel()])

        self.tree = cKDTree(self.points)
        self.dist, self.idx = self.tree.query(target_points, k=1)

    @classmethod
    def from_files(cls, tiff_path: Path, wrf_path: Path):
        with rasterio.open(tiff_path, "r") as src:
            target_crs = src.crs
            target_transform = src.transform
            width = src.width
            height = src.height

        wrf_lat, wrf_lon = read_wrf_coords(wrf_path)

        return cls(target_crs, target_transform, width, height, wrf_lat, wrf_lon)

    def resample(self, wrf_array):
        flat_vals = np.asarray(wrf_array).ravel()
        flat_vals = flat_vals[self.valid_mask]
        out = flat_vals[self.idx].reshape((self.height, self.width))

        outside = (
            (self.target_x < self.minx)
            | (self.target_x > self.maxx)
            | (self.target_y < self.miny)
            | (self.target_y > self.maxy)
        )
        if np.any(outside):
            out = out.astype(np.float32, copy=True)
            out[outside] = np.nan
        return out


def update_tiff_with_wrf(tiff_path: Path, out_path: Path, day_vars, next_vars, resampler=None):
    with rasterio.open(tiff_path, "r") as src:
        data = src.read()
        profile = src.profile

    height, width = data.shape[1], data.shape[2]
    if resampler is not None:
        day_vars = {k: resampler.resample(v) for k, v in day_vars.items()}
        next_vars = {k: resampler.resample(v) for k, v in next_vars.items()}
    elif day_vars["t2"].shape != (height, width):
        print(
            f"Shape mismatch for {tiff_path}: tiff {height}x{width} vs wrf {day_vars['t2'].shape}. "
            "Provide a resampler to handle mismatched grids."
        )
        return False

    day_speed, day_dir = wind_speed_and_dir(day_vars["u10"], day_vars["v10"])
    next_speed, next_dir = wind_speed_and_dir(next_vars["u10"], next_vars["v10"])

    dtype = data.dtype

    data[5, :, :] = day_vars["rain"].astype(dtype, copy=False)
    data[6, :, :] = day_speed.astype(dtype, copy=False)
    data[7, :, :] = day_dir.astype(dtype, copy=False)
    data[8, :, :] = day_vars["t2_min"].astype(dtype, copy=False)
    data[9, :, :] = day_vars["t2_max"].astype(dtype, copy=False)
    data[11, :, :] = day_vars["q2"].astype(dtype, copy=False)

    data[17, :, :] = next_vars["rain"].astype(dtype, copy=False)
    data[18, :, :] = next_speed.astype(dtype, copy=False)
    data[19, :, :] = next_dir.astype(dtype, copy=False)
    data[20, :, :] = next_vars["t2"].astype(dtype, copy=False)
    data[21, :, :] = next_vars["q2"].astype(dtype, copy=False)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(data)

    return True


def _process_tiff_task(task):
    (
        tiff_path_str,
        out_path_str,
        day_files,
        next_files,
        overwrite,
        verbose,
    ) = task
    tiff_path = Path(tiff_path_str)
    out_path = Path(out_path_str)

    if out_path.exists() and not overwrite:
        return ("skipped", f"exists: {tiff_path}")

    try:
        resampler = WRFResampler.from_files(tiff_path, Path(day_files[0]))
    except Exception as exc:
        return ("skipped", f"resampler failed for {tiff_path}: {exc}")

    try:
        day_vars = average_wrf_files([Path(p) for p in day_files])
        next_vars = average_wrf_files([Path(p) for p in next_files])
    except (KeyError, ValueError, RuntimeError) as exc:
        return ("skipped", f"{tiff_path}: {exc}")

    updated = update_tiff_with_wrf(
        tiff_path, out_path, day_vars, next_vars, resampler=resampler
    )
    if not updated:
        return ("skipped", f"update failed: {tiff_path}")

    if verbose:
        return ("written", f"wrote: {out_path}")
    return ("written", None)


def build_wrf_wsts(
    wsts_dir: Path,
    wrf_dir: Path,
    out_dir: Path,
    overwrite: bool,
    log_every: int,
    verbose: bool,
    workers: int,
):
    years = sorted([p for p in wsts_dir.iterdir() if p.is_dir() and p.name.isdigit()])
    if not years:
        raise RuntimeError(f"No year directories found in {wsts_dir}")

    total_written = 0
    total_skipped = 0
    total_seen = 0

    tasks = []
    for year_dir in years:
        year = year_dir.name
        fire_dirs = sorted([p for p in year_dir.iterdir() if p.is_dir()])
        print(f"Year {year}: {len(fire_dirs)} fires")
        for fire_dir in fire_dirs:
            fire_name = fire_dir.name
            fire_wrf_dir = wrf_dir / fire_name
            if not fire_wrf_dir.exists():
                continue

            wrf_index = index_wrf_files(fire_wrf_dir)
            if not wrf_index:
                continue

            tiffs = sorted(fire_dir.glob("*.tif"))
            print(f"  Fire {fire_name}: {len(tiffs)} tiffs, {len(wrf_index)} WRF days")

            for tiff_path in tiffs:
                date_str = tiff_path.stem
                out_path = out_dir / year / fire_name / tiff_path.name

                if date_str not in wrf_index:
                    if verbose:
                        print(f"    skip (no WRF day): {tiff_path}")
                    total_skipped += 1
                    continue

                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                next_date_str = (date_obj + timedelta(days=1)).strftime("%Y-%m-%d")
                if next_date_str not in wrf_index:
                    if verbose:
                        print(f"    skip (no next-day WRF): {tiff_path}")
                    total_skipped += 1
                    continue

                day_files = wrf_index[date_str]
                next_files = wrf_index[next_date_str]
                if not day_files or not next_files:
                    if verbose:
                        print(f"    skip (empty WRF list): {tiff_path}")
                    total_skipped += 1
                    continue

                tasks.append(
                    (
                        str(tiff_path),
                        str(out_path),
                        [str(p) for p in day_files],
                        [str(p) for p in next_files],
                        overwrite,
                        verbose,
                    )
                )

    if workers is None or workers < 1:
        workers = 0

    if workers == 0 or len(tasks) == 0:
        for task in tasks:
            total_seen += 1
            if log_every > 0 and total_seen % log_every == 0:
                print(f"Progress: seen {total_seen}, wrote {total_written}, skipped {total_skipped}")
            status, msg = _process_tiff_task(task)
            if status == "written":
                total_written += 1
            else:
                total_skipped += 1
            if msg:
                print(msg)
    else:
        max_workers = min(workers, os.cpu_count() or workers)
        print(f"Running with {max_workers} workers over {len(tasks)} tasks.")
        with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
            future_to_task = {executor.submit(_process_tiff_task, task): task for task in tasks}
            for future in concurrent.futures.as_completed(future_to_task):
                total_seen += 1
                if log_every > 0 and total_seen % log_every == 0:
                    print(f"Progress: seen {total_seen}, wrote {total_written}, skipped {total_skipped}")
                try:
                    status, msg = future.result()
                except Exception as exc:
                    status, msg = "skipped", f"task failed: {exc}"
                if status == "written":
                    total_written += 1
                else:
                    total_skipped += 1
                if msg:
                    print(msg)

    print(f"Done. Wrote {total_written} files, skipped {total_skipped}.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wsts_dir", type=str, required=True, help="Path to WSTS directory.")
    parser.add_argument("--wrf_dir", type=str, required=True, help="Path to wrfout_fire directory.")
    parser.add_argument("--out_dir", type=str, required=True, help="Path to output wrf_wsts directory.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files.")
    parser.add_argument("--log_every", type=int, default=200, help="Log progress every N tiffs.")
    parser.add_argument("--verbose", action="store_true", help="Verbose per-file logging.")
    parser.add_argument("--workers", type=int, default=0, help="Number of worker processes (0=sequential).")
    args = parser.parse_args()

    build_wrf_wsts(
        Path(args.wsts_dir),
        Path(args.wrf_dir),
        Path(args.out_dir),
        args.overwrite,
        args.log_every,
        args.verbose,
        args.workers,
    )


if __name__ == "__main__":
    main()
