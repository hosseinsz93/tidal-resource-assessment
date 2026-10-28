# Run settings

Edit **config.json**, beside `Tidal_Resource_Assessment.ipynb`. This is the single active
configuration for all data, quality, flow, profile, turbine and comparison parameters.
Settings are grouped into four objects. Put each key inside the object named below.
Run the notebook from top to bottom after saving changes. No configuration path needs editing.
Data and turbine CSV paths remain relative to the repository and inside `inputs/`.

| Object | What belongs here |
|---|---|
| `data_and_quality` | Source, site, input path, time, depth datum, Verdant sheets, exclusions, speed and coverage limits, water depth |
| `flow_cycles_profiles` | Channel axis, cycles, residual window, profiles |
| `turbine_and_power` | Hub bin, cut-in, rated speed, cut-off, power curve and single-turbine AEP |
| `comparisons` | Annual prediction-event comparison |

To switch sources, edit these fields in the same file (also review the site-specific flood
bearing, depth metadata and turbine assumptions):

| Field | CO-OPS supplied data | Verdant supplied data | Other ADCP |
|---|---|---|---|
| source | `coops` | `verdant` | `standard_csv` |
| site | `LIS1016` | `Verdant_B` | Your site name |
| input_path | `inputs/coops/depth_bins` | `inputs/verdant` | `inputs/custom/my_adcp.csv` |
| time_zone | `unspecified` | `UTC` | Actual timestamp reference |
| excluded_bins | `[]` | `[45,46,47,48,49]` | Reviewed exclusions |
| water_depth_m | `47.18` (automatic LIS1016 preset) | `26.9` (Station B) or `24.0` (Station A) | Confirmed site depth or `null` |
| ensemble_minutes | `60` | `10` | Instrument ensemble length |
| hub_bin | `13` | `13` | Existing selected bin |

Verdant sheet names and heading offsets are already present in the global file. Parameters
specific to an inactive source are ignored. Slack is derived automatically from cut-in.

## Water depth

Add the total water depth at the ADCP in `data_and_quality.water_depth_m`, in metres. Only
one value is active at a time; change it whenever you switch source or Verdant station. Use
`null` if the depth is unknown (physical log-law fits are then skipped). Station presets
fill this field automatically for LIS1016 and the Verdant sheets. Heights below are height
above bed (HAB).

| Site | `water_depth_m` | Reported bins | Retained HAB | Source |
|---|---|---|---|---|
| Verdant Station A | `24.0` | 43 (1.67–22.67 m) | bins 1–38, 1.67–20.17 m | ADCP workbook geometry |
| Verdant Station B (current `config.json`) | `26.9` | 49 (1.67–25.67 m) | bins 1–44, 1.67–23.17 m | ADCP workbook geometry |
| CO-OPS LIS1016 | `47.18` | 17 (9.41–41.42 m) | all 17 bins, 9.41–41.42 m | Pressure-derived NOAA depth |

For a new site, enter the confirmed deployment or station depth and geometry.

### CO-OPS LIS1016

When `source` is `coops` and `site` is `LIS1016`, the loader applies the verified NOAA
deployment metadata automatically. LIS1016 is at 41.18945°N, 72.36960°W (Cornfield Point,
4 miles south of Buoy CF). NOAA identifies a four-beam, 300 kHz Teledyne RDI Workhorse ADCP,
upward-looking, 5.18 m above the seabed. Nominal water depth is 47.0 m; the pressure-derived
measured depth used for heights is 47.18 m. Valid observations run from 9 June to 27 July
2010 at a 360 s (6 min) interval. The flood-reference bearing is 250°.

The deployment has 17 cells of 2.0 m, with the centre of bin 1 located 4.23 m above the
instrument. NOAA reports cell depths from 37.77 m to 5.76 m below the surface. Bin numbers
increase upward from the bed: bin 1 is the 37.77 m depth-below-surface cell. Heights are

```
z_i = 47.18 − d_i
```

where `d_i` is the NOAA depth below the surface, giving 9.41–41.42 m HAB. The same
coordinate is reconstructed from the instrument geometry as

```
z_i = 5.18 + 4.23 + 2.0 × (i − 1)
```

The two calculations agree within 0.01 m. For example, the cell at 21.76 m below the
surface is bin 9 and lies 25.42 m above the bed. The preset uses `near_bed_fraction = 0.30`,
which includes the lowest three cells in the physical log-law fit.

See the official [deployment metadata](https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/LIS1016/deployments.json)
and [bin metadata](https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/LIS1016/bins.json).

### Verdant stations

Each Verdant workbook holds two stations. Choose one station for both deployment periods by
setting only `verdant_sheets`. The heading offsets, excluded bins and water depth below are then
filled in automatically. A value written explicitly in `config.json` overrides the preset; leave
those keys out unless you mean to override them. Sheet names without a preset require all three.

| Field | Station B (current `config.json`) | Station A |
|---|---|---|
| verdant_sheets | `["Station B", "Station B-2"]` | `["Station A", "Station A-2"]` |
| site | `Verdant_B` | `Verdant_A` |
| verdant_heading_offsets | `[-5.53, 3.2]` | `[-0.07, 0.04]` |
| excluded_bins | `[45, 46, 47, 48, 49]` | `[39, 40, 41, 42, 43]` |
| water_depth_m | `26.9` | `24.0` |

Exported run folders, CSV names and figure files include the station tag
(`StationA` or `StationB`), e.g. `outputs/csv/Verdant_A_verdant_StationA_<timestamp>/`
and `StationA_energy_bins.csv`. Figure titles also show the station.

The Verdant workbooks give each cell as both distance above the bed and distance from the
ADCP head. At Stations A and B the centre of bin 1 is 1.67 m above the bed and 1.21 m from
the instrument head, so the head sits 0.46 m above the bed. Cells are spaced 0.50 m:

```
z_i = 1.67 + 0.50 × (i − 1)
```

Station A reports 43 bins spanning 1.67–22.67 m HAB. Station B reports 49 bins spanning
1.67–25.67 m HAB. The upper five bins at each station are excluded to limit near-surface
interference (bins 39–43 at A, 45–49 at B). Retained profiles are therefore bins 1–38
(1.67–20.17 m) at Station A and bins 1–44 (1.67–23.17 m) at Station B. Total water depths
of 24.0 m and 26.9 m are used when normalizing by water-column depth. Both records run
from 23 October 2024 to 15 February 2025 at a 10 min interval.

The excluded bins are the uppermost, near-surface cells. Their valid-velocity fraction falls
below 100% in at least one deployment period, usually from changing water level or surface
interference. The second deployment loses more near the surface than the first.

Valid-velocity fraction by sheet, for every bin that is not fully valid:

| Bin | Station A | Station A-2 | Station B | Station B-2 |
|---|---|---|---|---|
| 39 | 100% | 96.7% | 100% | 100% |
| 40 | 80.4% | 62.3% | 100% | 100% |
| 41 | 42.3% | 26.6% | 100% | 100% |
| 42 | 8.2% | 1.7% | 100% | 100% |
| 43 | 0.3% | 0% | 100% | 100% |
| 45 | — | — | 100% | 95.5% |
| 46 | — | — | 85.4% | 59.3% |
| 47 | — | — | 45.8% | 23.8% |
| 48 | — | — | 10.0% | 1.2% |
| 49 | — | — | 0.6% | 0% |

Bins 1–38 (Station A) and 1–44 (Station B) are 100% valid in both periods. Bins 44 and 45–49
do not exist at Station A. Bin 44 is fully valid at Station B, so it is kept.

`min_bin_coverage` of `1.0` requires every retained bin to be valid at a timestamp. Without
the exclusions, almost no timestamp meets that rule, and Process stops because fewer than half
of the depth averages pass coverage. After the exclusions above, every remaining bin is 100%
valid, so every timestamp passes. Do not lower `min_bin_coverage` instead: the depth average
would then use a different set of bins at different times.

Excluding a bin that is not in the selected station is an error. Station B's list cannot be
used for Station A, and the reverse also fails. The station presets avoid this; the notebook
setup panel applies the same presets when the sheet names change.

Heading offsets use the original orientation-correction method: the arithmetic mean of the
first `Dir` column over both periods minus that period's mean. This method reproduces the B
values exactly. Station A flows near north (circular mean about 9°), so its directions wrap
through 0°/360° and an arithmetic mean is unreliable. Circular means give A offsets of about
`[-2.18, 1.18]` (and B `[-1.13, 0.83]`). Confirm A's offsets before relying on direction results.

Use numbers without quotes, arrays in square brackets, and lowercase `true`, `false`,
and `null`. JSON does not allow comments or trailing commas. Unknown or duplicate keys
and incorrect value types produce an error. The global file specifies all configurable fields;
omitted optional fields use backend defaults. Slack is derived from cut-in, not a separate input.

## Data and quality

| Key | Meaning |
|---|---|
| source | `coops`, `verdant`, or `standard_csv` |
| site | Site/run name; for CO-OPS must match filename prefix; letters, digits, `_`, `-` |
| input_path | Observation folder or standard CSV path |
| time_zone | Source timestamp reference; `unspecified` if unknown; Verdant uses UTC |
| coops_depth_reference | `unknown`, `below_surface`, or `above_bed`; confirm from metadata |
| coops_adcp_orientation | `unknown`, `upward`, or `downward`; controls the physical CO-OPS bin order |
| coops_nominal_water_depth_m | Nominal deployment depth, m, or `null`; LIS1016 preset: 47.0 |
| coops_instrument_height_above_bed_m | Instrument elevation above bed, m, or `null`; LIS1016 preset: 5.18 |
| coops_bin1_center_distance_m | Distance from the instrument to bin-1 center, m, or `null`; LIS1016 preset: 4.23 |
| coops_bin_size_m | Measurement-cell spacing, m, or `null`; LIS1016 preset: 2.0 |
| verdant_sheets | Sheet names corresponding to alphabetically sorted workbooks |
| verdant_heading_offsets | Matching heading corrections in degrees; Station B `[-5.53, 3.2]`, Station A `[-0.07, 0.04]` |
| excluded_bins | Integer bin IDs to exclude; Verdant Station B excludes 45–49, Station A 39–43 (see Verdant stations) |
| max_speed_mps | Maximum accepted horizontal speed, m/s |
| min_bin_coverage | Fraction of selected bins required for a valid depth average, (0,1] |
| water_depth_m | Total water depth at the ADCP in metres, or `null`. Known sites: Verdant Station A 24.0 (retained HAB 1.67–20.17 m), Station B 26.9 (retained HAB 1.67–23.17 m); CO-OPS LIS1016 47.18 (HAB 9.41–41.42 m) from [NOAA deployment metadata](https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/LIS1016/deployments.json) |

## Flow, cycles, profiles and variability

| Key | Meaning |
|---|---|
| axis_method | How the principal flood–ebb axis is calculated from the data: `pca` (velocity-weighted spread) or `doubled_angle` (direction-only mean) |
| flood_reference_deg | Label hint only, degrees true. The axis is always calculated; this picks which of its two ends is called flood (the end closer to this bearing). It does not move the axis |
| smooth_samples | Positive integer window for phase-classification smoothing |
| gap_factor | Gap threshold relative to nominal sampling interval; greater than 1 |
| min_cycle_hours, max_cycle_hours | Accepted full-cycle duration range in hours |
| ensemble_minutes | Rolling residual window in minutes; positive integer. Use `60` for CO-OPS and `10` for Verdant; the current `config.json` is Verdant, so it is `10` |
| noise_std_mps | Supplied velocity-noise standard deviation in m/s; zero if not estimated |
| near_bed_fraction | Maximum z/h for physical log fit, (0,1]; legacy mode may expand it |
| profile_coordinate_mode | `legacy_normalized` or `physical`; inferred legacy coordinates are not measured z/h |

## Turbine and power curve

| Key | Meaning |
|---|---|
| energy_enabled | Compute single-turbine IEC AEP, `true` or `false` |
| hub_bin | Measurement bin used for energy; must exist in selected data |
| cut_in_mps | Cut-in speed, m/s; also sets slack to absolute smoothed along velocity ≤ this value |
| rated_speed_mps | Rated speed, m/s; must lie strictly between cut-in and cut-off |
| cut_out_mps | Cut-off speed, m/s; power is zero at and above it |
| rated_kw | Positive rated turbine power, kW; supplied curve must not exceed it |
| power_curve_mode | `csv`, `edited`, or `generated`. `generated` uses P = ½ρAC<sub>p</sub>ηU³ from cut-in to rated, rated power up to cut-out, zero elsewhere |
| rotor_diameter_m | Rotor diameter, m (`generated` only). With a value, rated speed is computed from rated power; `null` derives the swept area from rated power at `rated_speed_mps` |
| power_coefficient | Hydrodynamic C<sub>p</sub>, at most the Betz limit 16/27; typically 0.35–0.45 |
| drivetrain_efficiency | Gearbox, generator and power-electronics efficiency η, in (0, 1]; typically 0.90–0.95 |
| water_density_kgm3 | Seawater density ρ, kg/m³ (1025 typical) |
| power_curve | CSV path used only in `csv` mode; columns `speed_mps,power_kw` |
| power_curve_points | Array of `[speed_mps, power_kw]` pairs, used only in `edited` mode |
| speed_bin_width | Positive speed-bin width for energy integration, m/s |
| turbine_count | Retained for compatibility; energy results are for a single turbine and do not use it |
| availability | Energy availability multiplier, (0,1] |

For example, set `power_curve_mode` to `edited` and revise:

```json
"power_curve_points": [[0, 0], [0.4, 0], [1, 25], [2, 110], [3.2, 110]]
```

This is a field fragment to place inside the settings object. Speeds must be unique;
both speeds and powers must be finite and nonnegative. CSV/edited curves use linear
interpolation and preserve your shape. They must cover occupied operating speed bins.
Changing rated speed does not reshape a supplied curve. `generated` mode instead uses
an idealized cubic rise from zero at cut-in to rated power at rated speed, then a plateau.
All modes enforce cut-in and cut-off. Review `turbine_power_curve` in the result gallery.

The supplied global `config.json` defaults to `edited`, so it is self-contained and uses
the `power_curve_points` stored in that same file. Set the mode to `csv` only when you
have placed the named power-curve file under `inputs/`.

## Optional comparisons

| Key | Meaning |
|---|---|
| compare_annual_records | Enable separate annual prediction-event comparisons |
| annual_input_path | Folder containing annual-event CSVs |

Changing `source` alone does not change other settings. Review headings, depth metadata, flood bearing, bin exclusions and turbine settings.
Preprocess reloads the saved JSON; rerun all three stages after edits. Result exploration
can remain interactive, but configuration requires no widgets. Every run preserves the
effective settings in its run log (`run_log.json`) and exports the selected curve as CSV.

## Analyses and conventions

The JSON file accepts cut-in, rated speed, cut-off speed, and rated power.
Slack always uses the cut-in threshold, including when energy estimation is disabled.
Choose a CSV curve, edit the JSON speed–power pairs, or generate an
idealized cubic-rise/rated-plateau curve. Review the exported curve; revised points are
stored in the run settings and exported curve. Rated speed shapes generated curves;
CSV/edited points retain their supplied shape. Cut-in/cut-off apply to every curve.
Velocity profiles show negative ebb on the left and positive flood on the right.

- Unit/metadata validation, duplicate/overlap checks, depth-bin coverage and gap detection.
- True-bearing channel axes calculated by PCA or doubled-angle directions; a flood-end hint only labels which end is flood.
- One phase label per timestamp: positive along-channel = flood; negative = ebb; missing remains missing. Depth-resolved analyses inherit the same label.
- Gap-aware cycle segmentation, normalized ensemble cycles and harmonic fits.
- Phase-mean vertical profiles and separate event-peak profiles; power/log fits when physical height metadata support them.
- Rolling-residual intensity by depth/phase, with optional supplied instrument-noise variance subtraction.
- Time-weighted hub-bin speed distributions, power-curve integration and single-turbine AEP (IEC TS 62600-200, 8,766 h/yr).
- Consistent red flood / blue ebb / grey slack figures, with bin/phase/time exploration. The
  tidal-velocity polar figure follows the principal-flow diagnostics and shows valid bin vectors,
  the bidirectional principal axis, phase-mean bearings and phase-mean speeds for every source.

The example flood reference and turbine are specific to Long Island Sound. Check these for a new site. The backend uses named columns rather than legacy positional layouts. Depth averages are arithmetic vector means over measured bins. Sample weights assume ensemble-start timestamps, cap support across large gaps at nominal cadence, and assign one nominal interval to the last record.

**Scientific scope:** six/ten-minute averaged velocities provide resolved variability, not full burst-scale turbulence. The workflow does not infer a noise floor spectrally from these coarse records. Unknown depth datum is never guessed from velocity gradients; unsupported physical fits are skipped. LIS1016 uses verified NOAA deployment geometry. Log fitting requires total water depth and three near-bed points. AEP assumes a representative annual distribution. This implementation is not an IEC certification.

Original normalized profile fits and original TI definitions are retained separately from physical-coordinate fits and newer residual-intensity measures; legacy inferred coordinates are not physical bed geometry.

Annual CO-OPS event predictions are **not** ADCP observations. Their original station/cycle comparisons are available as optional diagnostics, separate from measured resource and energy calculations. Arbitrary instrument file formats require conversion to the [standard CSV](inputs/custom/README.md) or a new source adapter.
