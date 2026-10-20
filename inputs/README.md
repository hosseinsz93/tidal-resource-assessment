# All inputs live here

Choose the source and path in `Tidal_Resource_Assessment.ipynb`.

| Folder | Contents | Active adapter |
|---|---|---|
| `coops/depth_bins/` | Measured speed and true direction per depth | CO-OPS |
| `verdant/` | Supplied deployment Excel workbooks | Verdant Power |
| `custom/` | Standardized data from another ADCP | Standard CSV |
| `turbine/` | Speed-to-power curves | Energy calculation |
| `coops/annual/` | Nonuniform event predictions | Reference only |

CO-OPS filenames: `<site>_<meters>m<centimeters>cm-<start-date>.csv`, for example `LIS1016_05m76cm-2010-06-09.csv`. Columns must include Date/Time, Speed with units (cm/sec, m/s, mm/s, or knots), and Dir (true). Multiple segments per bin are concatenated by timestamp. Select a single site prefix. Confirm time zone and depth datum from the download/deployment metadata. LIS1016 has a verified station preset: its depths are below surface, its pressure-derived water depth is 47.18 m, and its upward-looking bin geometry converts the supplied cells to 9.41--41.42 m above bed. Other CO-OPS sites require their confirmed depth reference, total depth, orientation, and cell geometry in `config.json`.

Verdant defaults select Station B/B-2 in filename order. The notebook preset excludes bins 45–49, which have poor coverage in these workbooks; the first 44 bins are complete. This exclusion is visible and editable. The adapter reads distance-from-bed metadata, east/north units and UTC timestamps, then applies the explicitly configured heading offsets to both vector components. Set `water_depth_m` in `config.json` to 26.9 for Station B or 24.0 for Station A. Other workbook layouts should be converted to the standard format or given a dedicated adapter.

Power curves require `speed_mps,power_kw` with unique speeds and finite nonnegative values. The curve must cover occupied operating-speed bins and must not exceed the rated power selected in the notebook. The supplied curve is an example, not a universal turbine specification.
