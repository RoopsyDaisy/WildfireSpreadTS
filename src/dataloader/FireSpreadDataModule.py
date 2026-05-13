from pathlib import Path

import numpy as np
import torch
from pytorch_lightning import LightningDataModule
from torch.utils.data import Subset, DataLoader
import glob
from .FireSpreadDataset import FireSpreadDataset
from typing import List, Optional, Union


class FireSpreadDataModule(LightningDataModule):

    def __init__(self, data_dir: str, batch_size: int, n_leading_observations: int, n_leading_observations_test_adjustment: int,
                 crop_side_length: int,
                 load_from_hdf5: bool, num_workers: int, remove_duplicate_features: bool,
                 load_from_zarr: bool = False,
                 is_pad: Optional[bool] = False,
                 features_to_keep: Union[Optional[List[int]], str] = None, return_doy: bool = False,
                 data_fold_id: int = 0, non_outlier_indices_path: Optional[str] = None, filter_ignition_train: Optional[bool] = False, filter_ignition_val_test: Optional[bool] = False,
                 ignition_only_train: Optional[bool] = False, ignition_only_val_test: Optional[bool] = False, additional_data: Optional[bool] = False,
                 split_strategy: str = "spatial", spatial_split_axis: str = "lon", spatial_split_folds: int = 4,
                 stats_years: Optional[List[int]] = None, wrf_data: bool = False, *args, **kwargs):
        """_summary_ Data module for loading the WildfireSpreadTS dataset.

        Args:
            data_dir (str): _description_ Path to the directory containing the data.
            batch_size (int): _description_ Batch size for training and validation set. Test set uses batch size 1, because images of different sizes can not be batched together.
            n_leading_observations (int): _description_ Number of days to use as input observation. 
            n_leading_observations_test_adjustment (int): _description_ When increasing the number of leading observations, the number of samples per fire is reduced.
              This parameter allows to adjust the number of samples in the test set to be the same across several different values of n_leading_observations, 
              by skipping some initial fires. For example, if this is set to 5, and n_leading_observations is set to 1, the first four samples that would be 
              in the test set are skipped. This way, the test set is the same as it would be for n_leading_observations=5, thereby retaining comparability 
              of the test set.
            crop_side_length (int): _description_ The side length of the random square crops that are computed during training and validation.
            load_from_hdf5 (bool): _description_ If True, load data from HDF5 files instead of TIF.
            load_from_zarr (bool): _description_ If True, load data from Zarr instead of TIF.
            num_workers (int): _description_ Number of workers for the dataloader.
            remove_duplicate_features (bool): _description_ Remove duplicate static features from all time steps but the last one. Requires flattening the temporal dimension, since after removal, the number of features is not the same across time steps anymore.
            features_to_keep (Union[Optional[List[int]], str], optional): _description_. List of feature indices from 0 to 39, indicating which features to keep. Defaults to None, which means using all features.
            return_doy (bool, optional): _description_. Return the day of the year per time step, as an additional feature. Defaults to False.
            data_fold_id (int, optional): _description_. Which data fold to use, i.e. splitting years into train/val/test set. Defaults to 0.
            split_strategy (str, optional): _description_. "year" or "spatial".
            spatial_split_axis (str, optional): _description_. "lon" or "lat".
            spatial_split_folds (int, optional): _description_. Number of spatial folds (used for val/test cycling).
            stats_years (Optional[List[int]], optional): _description_. Override years to use for mean/std statistics.
        """
        super().__init__()

        self.n_leading_observations_test_adjustment = n_leading_observations_test_adjustment
        self.data_fold_id = data_fold_id
        self.return_doy = return_doy
        # wandb apparently can't pass None values via the command line without turning them into a string, so we need this workaround
        self.features_to_keep = features_to_keep if type(
            features_to_keep) != str else None
        self.remove_duplicate_features = remove_duplicate_features
        self.num_workers = num_workers
        self.load_from_hdf5 = load_from_hdf5
        self.load_from_zarr = load_from_zarr
        self.crop_side_length = crop_side_length
        self.n_leading_observations = n_leading_observations
        self.data_dir = data_dir
        self.batch_size = batch_size
        self.train_dataset, self.val_dataset, self.test_dataset = None, None, None
        self.is_pad=is_pad
        self.non_outlier_indices_path = non_outlier_indices_path
        self.filter_ignition_train = filter_ignition_train
        self.filter_ignition_val_test = filter_ignition_val_test
        self.ignition_only_train = ignition_only_train
        self.ignition_only_val_test = ignition_only_val_test
        self.additional_data = additional_data
        self.split_strategy = split_strategy
        self.spatial_split_axis = spatial_split_axis
        self.spatial_split_folds = spatial_split_folds
        self.stats_years = stats_years
        self.wrf_data = wrf_data


    def keep_ignition(self, dataset):
        ignition_indices = []
        total_samples = len(dataset)
        kept = 0
        
        for idx in range(total_samples):
            sample = dataset[idx]
            inputs = sample[0]  # Shape: [1, 7, 128, 128]
            x_af = inputs[:, -1, :, :]  # Active fire mask
            
            # Check current fire presence
            if torch.sum(x_af == 1) < 1:  # Original filtering condition
                ignition_indices.append(idx)
                kept += 1
    
        # Print detailed statistics
        print(f"Total samples: {total_samples}")
        print(f"Kept samples (ignition): {kept} ({kept/total_samples:.2%})")
        print(f"Discarded samples: {total_samples - kept} ({(total_samples - kept)/total_samples:.2%})")
        return Subset(dataset, ignition_indices)

    def filter_dataset(self, dataset):
        valid_indices = []
        total_samples = len(dataset)
        kept = 0
        for idx in range(total_samples):
            sample = dataset[idx]
            inputs = sample[0]  # Shape: [1, 7, 128, 128] if T=1; but [5*N, 128, 128] if T=5, where N is the number of features
            if len(inputs.shape) == 3:
                x_af = inputs[-1, :, :]
            else:
                x_af = inputs[:, -1, :, :]  # Active fire mask
            
            # Check current fire presence
            if torch.sum(x_af == 1) > 1:  # Original filtering condition
                valid_indices.append(idx)
                kept += 1
        
        # Print detailed statistics
        print(f"Total samples: {total_samples}")
        print(f"Kept samples (current fire): {kept} ({kept/total_samples:.2%})")
        print(f"Discarded samples: {total_samples - kept} ({(total_samples - kept)/total_samples:.2%})")
        
        return Subset(dataset, valid_indices)
        
    def setup(self, stage):
        train_years, val_years, test_years = None, None, None
        train_fire_ids, val_fire_ids, test_fire_ids = None, None, None

        if self.split_strategy == "year":
            train_years, val_years, test_years = self.split_fires_by_year(
                self.data_fold_id, self.additional_data)
        elif self.split_strategy == "spatial":
            train_fire_ids, val_fire_ids, test_fire_ids = self.split_fires_spatial(
                self.data_dir, self.load_from_hdf5, self.load_from_zarr, self.data_fold_id,
                self.spatial_split_folds, self.spatial_split_axis)
        else:
            raise ValueError(f"Unknown split_strategy {self.split_strategy}")

        stats_years = self.stats_years
        if stats_years is None:
            stats_years = train_years if train_years is not None else self.get_available_years(self.data_dir)

        self.train_dataset = FireSpreadDataset(data_dir=self.data_dir, included_fire_years=train_years,
                                               included_fire_ids=train_fire_ids,
                                               n_leading_observations=self.n_leading_observations,
                                               n_leading_observations_test_adjustment=None,
                                               crop_side_length=self.crop_side_length,
                                               load_from_hdf5=self.load_from_hdf5, is_train=True,
                                               load_from_zarr=self.load_from_zarr,
                                               remove_duplicate_features=self.remove_duplicate_features,
                                               features_to_keep=self.features_to_keep, return_doy=self.return_doy,
                                               stats_years=stats_years, is_pad=self.is_pad,
                                               wrf_data=self.wrf_data)
        
        if self.non_outlier_indices_path is not None:
            non_outlier_indices = np.load(self.non_outlier_indices_path).tolist()
            print(f"Subsetting train_loader using {self.non_outlier_indices_path}")
            self.train_dataset = Subset(self.train_dataset, non_outlier_indices)

        if self.filter_ignition_train:
            self.train_dataset = self.filter_dataset(self.train_dataset)

        if self.ignition_only_train:
            self.train_dataset = self.keep_ignition(self.train_dataset)

        
        self.val_dataset = FireSpreadDataset(data_dir=self.data_dir, included_fire_years=val_years,
                                             included_fire_ids=val_fire_ids,
                                             n_leading_observations=self.n_leading_observations,
                                             n_leading_observations_test_adjustment=None,
                                             crop_side_length=self.crop_side_length,
                                             load_from_hdf5=self.load_from_hdf5, is_train=True,
                                             load_from_zarr=self.load_from_zarr,
                                             remove_duplicate_features=self.remove_duplicate_features,
                                             features_to_keep=self.features_to_keep, return_doy=self.return_doy,
                                             stats_years=stats_years, is_pad=self.is_pad,
                                             wrf_data=self.wrf_data)
        self.test_dataset = FireSpreadDataset(data_dir=self.data_dir, included_fire_years=test_years,
                                              included_fire_ids=test_fire_ids,
                                              n_leading_observations=self.n_leading_observations,
                                              n_leading_observations_test_adjustment=self.n_leading_observations_test_adjustment,
                                              crop_side_length=self.crop_side_length,
                                              load_from_hdf5=self.load_from_hdf5, is_train=False,
                                              load_from_zarr=self.load_from_zarr,
                                              remove_duplicate_features=self.remove_duplicate_features,
                                              features_to_keep=self.features_to_keep, return_doy=self.return_doy,
                                              stats_years=stats_years, is_pad=self.is_pad,
                                              wrf_data=self.wrf_data)

        if self.filter_ignition_val_test:
            self.val_dataset = self.filter_dataset(self.val_dataset)
            self.test_dataset = self.filter_dataset(self.test_dataset)
            
        if self.ignition_only_val_test:
            self.val_dataset = self.keep_ignition(self.val_dataset)
            self.test_dataset = self.keep_ignition(self.test_dataset)

    def train_dataloader(self):
        return DataLoader(self.train_dataset, batch_size=self.batch_size, shuffle=True, num_workers=self.num_workers, pin_memory=True)

    def val_dataloader(self):
        return DataLoader(self.val_dataset, batch_size=self.batch_size, shuffle=False, num_workers=self.num_workers, pin_memory=True)

    def test_dataloader(self):
        return DataLoader(self.test_dataset, batch_size=1, shuffle=False, num_workers=self.num_workers, pin_memory=True)

    def predict_dataloader(self):
        return DataLoader(self.val_dataset, batch_size=self.batch_size, shuffle=False, num_workers=self.num_workers, pin_memory=True)

    @staticmethod
    def get_available_years(data_dir: str) -> List[int]:
        years = sorted([int(p.name) for p in Path(data_dir).iterdir()
                        if p.is_dir() and p.name.isdigit()])
        if not years:
            raise RuntimeError(f"No year directories found in {data_dir}")
        return years

    @staticmethod
    def collect_fire_records(data_dir: str, load_from_hdf5: bool, load_from_zarr: bool, years: List[int]):
        records = []
        if load_from_hdf5:
            try:
                import h5py
            except ImportError as exc:
                raise ImportError("h5py is required to read HDF5 metadata for spatial splits.") from exc
        elif load_from_zarr:
            try:
                import zarr
            except ImportError as exc:
                raise ImportError("zarr is required to read Zarr metadata for spatial splits.") from exc
        else:
            try:
                import rasterio
            except ImportError as exc:
                raise ImportError("rasterio is required to read TIFF metadata for spatial splits.") from exc

        for year in years:
            if load_from_hdf5:
                h5_files = glob.glob(f"{data_dir}/{year}/*.hdf5")
                h5_files.sort()
                for h5_path in h5_files:
                    fire_name = Path(h5_path).stem
                    with h5py.File(h5_path, "r") as f:
                        lnglat = f["data"].attrs.get("lnglat")
                    if lnglat is None:
                        continue
                    lon, lat = float(lnglat[0]), float(lnglat[1])
                    records.append((year, fire_name, lon, lat))
            elif load_from_zarr:
                zarr_dirs = glob.glob(f"{data_dir}/{year}/*.zarr")
                zarr_dirs.sort()
                for zarr_path in zarr_dirs:
                    fire_name = Path(zarr_path).stem
                    root = zarr.open_group(str(zarr_path), mode="r")
                    lnglat = root["data"].attrs.get("lnglat")
                    if lnglat is None:
                        continue
                    lon, lat = float(lnglat[0]), float(lnglat[1])
                    records.append((year, fire_name, lon, lat))
            else:
                fire_dirs = glob.glob(f"{data_dir}/{year}/*/")
                fire_dirs.sort()
                for fire_dir in fire_dirs:
                    fire_name = Path(fire_dir).name
                    tiff_paths = glob.glob(f"{fire_dir}/*.tif")
                    if not tiff_paths:
                        continue
                    tiff_paths.sort()
                    with rasterio.open(tiff_paths[0], "r") as ds:
                        bounds = ds.bounds
                    lon = (bounds.left + bounds.right) / 2
                    lat = (bounds.bottom + bounds.top) / 2
                    records.append((year, fire_name, lon, lat))

        return records

    @staticmethod
    def split_fires_spatial(data_dir: str, load_from_hdf5: bool, load_from_zarr: bool, data_fold_id: int,
                            n_folds: int = 4, axis: str = "lon"):
        years = FireSpreadDataModule.get_available_years(data_dir)
        records = FireSpreadDataModule.collect_fire_records(data_dir, load_from_hdf5, load_from_zarr, years)
        if not records:
            raise RuntimeError("No fires found to build spatial split.")

        if axis not in ("lon", "lat"):
            raise ValueError(f"spatial_split_axis must be 'lon' or 'lat', got {axis}")

        axis_index = 2 if axis == "lon" else 3
        other_index = 3 if axis_index == 2 else 2
        records_sorted = sorted(records, key=lambda x: (x[axis_index], x[other_index], x[1]))

        n_records = len(records_sorted)
        fold_sizes = [n_records // n_folds] * n_folds
        for i in range(n_records % n_folds):
            fold_sizes[i] += 1

        folds = []
        cursor = 0
        for size in fold_sizes:
            folds.append(records_sorted[cursor:cursor + size])
            cursor += size

        test_fold = data_fold_id % n_folds
        val_fold = (data_fold_id + 1) % n_folds

        train_records = [r for i, fold in enumerate(folds) if i not in (test_fold, val_fold) for r in fold]
        val_records = folds[val_fold]
        test_records = folds[test_fold]

        train_ids = [(r[0], r[1]) for r in train_records]
        val_ids = [(r[0], r[1]) for r in val_records]
        test_ids = [(r[0], r[1]) for r in test_records]

        print(
            f"Using spatial split ({axis}): train fires {len(train_ids)}, "
            f"val fires {len(val_ids)}, test fires {len(test_ids)}"
        )

        return train_ids, val_ids, test_ids

    @staticmethod
    def split_fires_by_year(data_fold_id, additional_data):
        """_summary_ Split the years into train/val/test set.

        Args:
            data_fold_id (_type_): _description_ Index of the respective split to choose, see method body for details.

        Returns:
            _type_: _description_
        """
        if not additional_data:

            folds = [(2018, 2019, 2020, 2021),
                 (2018, 2019, 2021, 2020),
                 (2018, 2020, 2019, 2021),
                 (2018, 2020, 2021, 2019),
                 (2018, 2021, 2019, 2020),
                 (2018, 2021, 2020, 2019),
                 (2019, 2020, 2018, 2021),
                 (2019, 2020, 2021, 2018),
                 (2019, 2021, 2018, 2020),
                 (2019, 2021, 2020, 2018),
                 (2020, 2021, 2018, 2019),
                 (2020, 2021, 2019, 2018)]
            train_years = list(folds[data_fold_id][:2])
            val_years = list(folds[data_fold_id][2:3])
            test_years = list(folds[data_fold_id][3:4])
        
        else:
            folds = [(2016, 2017, 2020, 2021, 2018, 2019, 2022, 2023),
                 (2018, 2019, 2022, 2023, 2020, 2021, 2016, 2017),
                 (2016, 2017, 2020, 2021, 2022, 2023, 2018, 2019),
                 (2018, 2019, 2022, 2023, 2016, 2017, 2020, 2021)]
            train_years = list(folds[data_fold_id][:4])
            val_years = list(folds[data_fold_id][4:6])
            test_years = list(folds[data_fold_id][6:8])

        print(
            f"Using the following dataset split:\nTrain years: {train_years}, Val years: {val_years}, Test years: {test_years}")

        return train_years, val_years, test_years
