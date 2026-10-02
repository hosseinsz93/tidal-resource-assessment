# Standard CSV for another ADCP

Save one CSV here and choose **Other ADCP: standard CSV** in the notebook. This is the adapter boundary for arbitrary instrument exports, not a claim that proprietary formats can all be parsed automatically.

```csv
time,bin,depth_m,depth_reference,east_mps,north_mps
2024-01-01T00:00:00,1,2.0,above_bed,0.2,0.1
2024-01-01T00:00:00,2,3.0,above_bed,0.3,0.1
2024-01-01T00:10:00,1,2.0,above_bed,0.25,0.1
2024-01-01T00:10:00,2,3.0,above_bed,0.35,0.1
```

- One row per timestamp and bin. Use at least three unique timestamps; scientific analyses need substantially longer records.
- `time`: consistent ISO ensemble-start timestamps. All timestamps must share a clock. Offset-aware times are converted to UTC; naive times retain the clock declared in settings. Do not mix aware and naive timestamps.
- `bin`: positive integer, stable across the record.
- `depth_m`: nonnegative coordinate in metres, fixed per bin.
- `depth_reference`: `above_bed`, `below_surface`, or `unknown`. Never infer these from velocity gradients.
- `east_mps`, `north_mps`: true east/north components in **m/s**, already corrected for heading and magnetic declination where applicable.
- Missing velocities are allowed. They remain missing and affect coverage; no interpolation is applied across them.
- Explicitly regrid deployments before merging if their measurement grids differ.

Once loaded, this format uses exactly the same analyses and exports as CO-OPS and Verdant.
