# CO-OPS Depth-Bin Inputs

This folder contains the NOAA CO-OPS current records read by `folderReadDF.ipynb`. Every `*.csv` here is loaded as one depth bin, so keep only depth-bin files in this folder.

## Format

Use:

```text
<site-id>_<meters>m<centimeters>cm-<YYYY-MM-DD>.csv
```

Example: `LIS1016_05m76cm-2010-06-09.csv`.

- The site ID comes from CO-OPS.
- The depth is encoded in metres and centimetres.
- The date is the first deployment date represented by that file.
- Split deployments use multiple files with the same site and depth but different dates.
- Each CSV must contain `Date/Time`, `Speed`, and `Dir` columns with units in the headers.
