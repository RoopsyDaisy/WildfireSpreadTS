# AGENT

Facts and requirements from the user prompt:
- This repo trains a fire prediction model on WildfireSpreadTS, with new WRF runs to improve the data.
- Build a WRF-enriched dataset by combining WSTS TIFFs with WRF NetCDF outputs.
- For each TIFF day, add WRF temperature (T2), precipitation (RAINC + RAINCC), wind (U10, V10), and humidity (Q2).
- If multiple NetCDF files exist for a day, average them.
- Forecast fields should use the next day’s NetCDF averages.
- If no current-day or next-day NetCDF data exist, skip that TIFF.
- Write enriched TIFFs to `wrf_wsts`.
- Use `/run/host/run/data_raid5/lornjaeger/trimmed` as the WRF source going forward, ignoring temp files.
- Build Zarr outputs in `wrf_wsts_zarr` instead of HDF5.
- Training should use a one-day input model (T=1).
- Replace year-based splits with spatial splits because year distribution is uneven.
- Keep the workflow simple so new data can be rsynced in and regenerated with minimal effort.
