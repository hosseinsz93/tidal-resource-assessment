# All inputs live here

Choose the source and path in `Tidal_Resource_Assessment.ipynb`.

| Folder | Contents | Active adapter |
|---|---|---|
| `coops/depth_bins/` | Measured speed and true direction per depth | CO-OPS |
| `verdant/` | Supplied deployment Excel workbooks | Verdant Power |
| `custom/` | Standardized data from another ADCP | Standard CSV |
| `turbine/` | Speed-to-power curves | Energy calculation |
| `coops/annual/` | Nonuniform event predictions | Reference only |

CO-OPS filenames: `<site>_<meters>m<centimeters>cm-<start-date>.csv`, for example `LIS1016_05m76cm-2010-06-09.csv`. Columns must include Date/Time, Speed with units (cm/sec, m/s, mm/s, or knots), and Dir (true). Multiple segments per bin are concatenated by timestamp. Select a single site prefix. Confirm time zone and depth datum from the download/deployment metadata. Total water depth is not read from these files; set `data_and_quality.water_depth_m` in `config.json` (LIS1016 is 37.8 m / 124 ft).

Verdant defaults select Station B/B-2 in filename order. The notebook preset excludes bins 45–49, which have poor coverage in these workbooks; the first 44 bins are complete. This exclusion is visible and editable. The adapter reads distance-from-bed metadata, east/north units and UTC timestamps, then applies the explicitly configured heading offsets to both vector components. Set `water_depth_m` in `config.json` to 26.9 for Station B or 24.0 for Station A. Other workbook layouts should be converted to the standard format or given a dedicated adapter.

Power curves require `speed_mps,power_kw` with unique speeds and finite nonnegative values. The curve must cover occupied operating-speed bins and must not exceed the rated power selected in the notebook. The supplied curve is an example, not a universal turbine specification.
