"""Per-channel mean / std / missing-value rate for the WRF-enriched dataset.

Computed by `scripts/compute_wrf_stats.py` over the WRF Zarr stores. These
override the original WSTS+ stats in `dataloader/utils.py` for runs that set
`wrf_data: true` in the data config — needed because `BuildWRFWSTS.py`
overwrites channels 5,6,7,8,9,11,17,18,19,20,21 with WRF values that have
different distributions from the original GRIDMET / GFS data those channels
held.

To re-derive (after preprocessing changes or a dataset migration):

    PYTHONPATH=$PWD:$PWD/src uv run python scripts/compute_wrf_stats.py \\
        --data_dir /run/data_raid5/scratch/wrf_wsts_zarr \\
        --years 2018 2019 2020 2021

The script filters out NetCDF sentinel-fill values (|x| > 1e10) which leak
into a couple of fires' rain channels — see STATUS.md and BACKLOG.
"""

from typing import List, Tuple

import numpy as np


WRF_STATS = {
    (2018, 2019, 2020, 2021): {
        "means": np.array(
            [
                1928.123779296875,    # ch0  VIIRS band M11
                3002.82763671875,     # ch1  VIIRS band I2
                1927.421997070312,    # ch2  VIIRS band I1
                4198.05517578125,     # ch3  NDVI
                2159.676513671875,    # ch4  EVI2
                0.4005341529846191,   # ch5  WRF day rain
                2.109230041503906,    # ch6  WRF day wind speed
                214.9757843017578,    # ch7  WRF day wind direction (deg)
                286.5184631347656,    # ch8  WRF day t2_min (K)
                296.6981506347656,    # ch9  WRF day t2_max (K)
                67.08428192138672,    # ch10 energy release component
                0.005251728463917971, # ch11 WRF day q2 (kg/kg)
                6.962762355804443,    # ch12 slope
                175.4844207763672,    # ch13 aspect (deg)
                1440.99365234375,     # ch14 elevation (m)
                -1.835738897323608,   # ch15 PDSI
                8.691513061523438,    # ch16 landcover (categorical)
                0.4151544868946075,   # ch17 WRF next-day rain
                2.243970632553101,    # ch18 WRF next-day wind speed
                215.3390502929688,    # ch19 WRF next-day wind direction (deg)
                291.5382080078125,    # ch20 WRF next-day t2 (K)
                0.005228869616985321, # ch21 WRF next-day q2 (kg/kg)
                0.0309108030050993,   # ch22 active fire (label)
            ],
            dtype=np.float32,
        ),
        "stds": np.array(
            [
                1169.389770507812,
                1704.984497070312,
                1992.28173828125,
                2227.446533203125,
                1087.926879882812,
                2.284143924713135,
                1.695667624473572,
                95.11936950683594,
                9.045435905456543,
                9.144185066223145,
                21.59861946105957,
                0.002482857089489698,
                6.784364700317383,
                103.0004043579102,
                799.056396484375,
                1.989341020584106,
                3.439278841018677,
                2.157406330108643,
                1.855512142181396,
                95.35298156738281,
                9.089849472045898,
                0.002491005463525653,
                0.7178359627723694,
            ],
            dtype=np.float32,
        ),
        "missing_values": np.array(
            [
                0.02996951900422573,
                0.02996299788355827,
                0.02996096946299076,
                0.04805580526590347,
                0.04805626720190048,
                0.000510804180521518,  # NetCDF sentinel pixels in 2 fires
                0.0,
                0.0,
                0.0,
                0.0,
                0.01057581510394812,
                0.0,
                0.01204056013375521,
                0.01204056013375521,
                0.0118148410692811,
                0.01398600544780493,
                0.0,
                0.000510804180521518,  # NetCDF sentinel pixels in 2 fires
                0.0,
                0.0,
                0.0,
                0.0,
                0.0,
            ],
            dtype=np.float32,
        ),
    },
}


def get_means_stds_missing_values_wrf(training_years: List[int]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """WRF-flavoured stats lookup, mirroring `utils.get_means_stds_missing_values`.

    Same post-processing rule as the WSTS+ stats: degree-based features and the
    categorical landcover channel are not standardized (mean=0, std=1).
    """
    from .utils import get_indices_of_degree_features

    years_tuple = tuple(training_years)
    if years_tuple not in WRF_STATS:
        raise KeyError(
            f"No WRF stats available for years {years_tuple}. "
            f"Available: {sorted(WRF_STATS.keys())}. "
            f"Recompute via scripts/compute_wrf_stats.py."
        )

    entry = WRF_STATS[years_tuple]
    means = entry["means"].copy()
    stds = entry["stds"].copy()
    missing_values = entry["missing_values"].copy()

    features_to_not_standardize = get_indices_of_degree_features() + [16]
    means[features_to_not_standardize] = 0
    stds[features_to_not_standardize] = 1

    return means, stds, missing_values
