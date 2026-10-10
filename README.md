# Tidal energy resource assessment

**Start with [Tidal_Resource_Assessment.ipynb](Tidal_Resource_Assessment.ipynb).** Edit the single [config.json](config.json) alongside it, then run **Preprocess → Process → Postprocess**. All input parameters are in this global file. See [CONFIGURATION.md](CONFIGURATION.md) for fields, units and source-switching instructions. The bundled CO-OPS defaults support Run All.

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

## Water depth

Add the total water depth at the ADCP in **[config.json](config.json)**, field `data_and_quality.water_depth_m`, in metres. Only one value is active at a time; change it whenever you switch source or Verdant station. Use `null` if the depth is unknown (physical log-law fits are then skipped).

| Site | `water_depth_m` | Source |
|---|---|---|
| Verdant Station A | `24.0` | ADCP deployment depth |
| Verdant Station B (current `config.json`) | `26.9` | ADCP deployment depth |
| CO-OPS LIS1016 (Cornfield Point, 4 miles south of Buoy CF) | `37.8` | 124 ft from [NOAA current predictions](https://tidesandcurrents.noaa.gov/noaacurrents/predictions.html?id=LIS1016_1) |

For a new site, enter the confirmed deployment or station depth in that same field. See [CONFIGURATION.md](CONFIGURATION.md).

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

Each export creates a new run folder.

## Analyses and conventions

The JSON file accepts cut-in, rated speed, cut-off speed, and rated power.
Slack always uses the cut-in threshold, including when energy estimation is disabled.
Choose a CSV curve, edit the JSON speed–power pairs, or generate an
idealized cubic-rise/rated-plateau curve. Review the exported curve; revised points are
stored in the run settings and exported curve. Rated speed shapes generated curves;
CSV/edited points retain their supplied shape. Cut-in/cut-off apply to every curve.
Velocity profiles show negative ebb on the left and positive flood on the right.

- Unit/metadata validation, duplicate/overlap checks, depth-bin coverage and gap detection.
- True-bearing channel axes by PCA, doubled-angle directions, or a supplied fixed flood bearing.
- One phase label per timestamp: positive along-channel = flood; negative = ebb; missing remains missing. Depth-resolved analyses inherit the same label.
- Gap-aware cycle segmentation, normalized ensemble cycles and harmonic fits.
- Phase-mean vertical profiles and separate event-peak profiles; power/log fits when physical height metadata support them.
- Rolling-residual intensity by depth/phase, with optional supplied instrument-noise variance subtraction.
- Time-weighted hub-bin speed distributions, power-curve integration and single-turbine AEP (IEC TS 62600-200, 8,766 h/yr).
- Consistent red flood / blue ebb / grey slack figures, with bin/phase/time exploration. The
  tidal-velocity polar figure follows the principal-flow diagnostics and shows valid bin vectors,
  the bidirectional principal axis, phase-mean bearings and phase-mean speeds for every source.

The example flood reference and turbine are specific to Long Island Sound. Check these for a new site. The backend uses named columns rather than legacy positional layouts. Depth averages are arithmetic vector means over measured bins. Sample weights assume ensemble-start timestamps, cap support across large gaps at nominal cadence, and assign one nominal interval to the last record.

**Scientific scope:** six/ten-minute averaged velocities provide resolved variability, not full burst-scale turbulence. The workflow does not infer a noise floor spectrally from these coarse records. Unknown depth datum is never guessed from velocity gradients; unsupported physical fits are skipped. Log fitting requires total water depth and three near-bed points. AEP assumes a representative annual distribution. This implementation is not an IEC certification.

All original postprocessing is accessible through the notebook's result-table selector and figure gallery. The exported checklist and [postprocessing mapping](backend/POSTPROCESSING_PARITY.md) identify the corresponding outputs. Original normalized profile fits and original TI definitions are retained separately from physical-coordinate fits and newer residual-intensity measures; legacy inferred coordinates are not physical bed geometry.

Annual CO-OPS event predictions are **not** ADCP observations. Their original station/cycle comparisons are available as optional diagnostics, separate from measured resource and energy calculations. Arbitrary instrument file formats require conversion to the [standard CSV](inputs/custom/README.md) or a new source adapter.

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
