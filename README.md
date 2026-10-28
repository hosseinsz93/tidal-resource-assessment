# Tidal energy resource assessment

This repository is a reproducible data analysis Python workflow for tidal-stream resource
assessment from ADCP measurements. It was developed for Long Island Sound using
NOAA CO-OPS station LIS1016 and Verdant Power deployments at two nearby sites
(Stations A and B). The same pipeline reads those sources, plus a documented
standard CSV for other instruments, then estimates principal-axis flow, tidal
cycles, vertical velocity and variability profiles, and single-turbine annual
energy production following IEC TS 62600-200.

**Start with [Tidal_Resource_Assessment.ipynb](Tidal_Resource_Assessment.ipynb).** Edit the single [config.json](config.json) alongside it, then run **Preprocess → Process → Postprocess**. All input parameters are in this global file. The bundled CO-OPS defaults support Run All.

The same backend handles NOAA CO-OPS depth-bin observations, the supplied Verdant Power workbooks, and a documented standard CSV for other ADCPs. Source adapters normalize measurements before any scientific analysis.

## Get started

From this repository's root:

```sh
conda env create -f environment.yml
conda activate resource-assesment
python -m ipykernel install --user --name resource-assesment --display-name "Python (resource-assesment)"
jupyter lab Tidal_Resource_Assessment.ipynb
```

Already have the environment? Update it with `conda env update -n resource-assesment -f environment.yml`, then select its kernel in Jupyter. Configuration uses JSON; optional result-table and figure exploration uses `ipywidgets`, included in the environment.

## Configuration

All parameters, units, source switching, water depth, and analysis conventions are in **[CONFIGURATION.md](CONFIGURATION.md)**. Edit `config.json` only.

## Where everything goes

```text
Tidal_Resource_Assessment.ipynb   Guided analysis and interactive exploration
config.json                     All user input parameters
CONFIGURATION.md                Parameter guide
inputs/                         All source data and turbine curves
  coops/depth_bins/              Main measured CO-OPS example
  coops/annual/                  Event predictions, retained for reference
  verdant/                      Original Excel workbooks
  custom/                       Other ADCPs in the standard CSV format
  turbine/                      Turbine power curves
outputs/
  csv/<site_source_run>/         Tables and run_log.json
  figures/<site_source_run>/     PNG figures
backend/
  tidal/                        Maintained loaders, calculations and notebook UI
  tests/                        Numerical and adapter regression tests
ADCP_Comparative_Analysis/       Manuscript and its existing figures
```

Each export creates a new run folder. Result tables and figures are listed in the notebook gallery and in the [postprocessing mapping](backend/POSTPROCESSING_PARITY.md). Other ADCP formats need the [standard CSV](inputs/custom/README.md) or a new source adapter.

## Reproducibility and development

Each run log saves source hashes, backend hashes, settings, software versions and interpretation notes. The manuscript is not updated automatically; new results may differ from historical outputs because the consolidated workflow fixes phase, column-position, gap and metadata inconsistencies.

```python
from pathlib import Path
from backend.tidal import Settings, preprocess, process, postprocess
assessment = preprocess(Path.cwd(), Settings())
process(assessment)
postprocess(assessment)
```

Run regression checks with `python -m pytest backend/tests`. See [backend/tidal/README.md](backend/tidal/README.md) for module boundaries and extension guidance.
