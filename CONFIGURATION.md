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
| water_depth_m | `37.8` (124 ft) | `26.9` (Station B) or `24.0` (Station A) | Confirmed site depth or `null` |
| ensemble_minutes | `60` | `10` | Instrument ensemble length |
| hub_bin | `13` | `13` | Existing selected bin |

Verdant sheet names and heading offsets are already present in the global file. Parameters
specific to an inactive source are ignored. Slack is derived automatically from cut-in.

### Verdant stations

Each Verdant workbook holds two stations. Choose one station for both deployment periods by
setting only `verdant_sheets`. The heading offsets, excluded bins and water depth below are then
filled in automatically. A value written explicitly in `config.json` overrides the preset; leave
those keys out unless you mean to override them. Sheet names without a preset require all three.

| Field | Station B | Station A (current `config.json`) |
|---|---|---|
| verdant_sheets | `["Station B", "Station B-2"]` | `["Station A", "Station A-2"]` |
| verdant_heading_offsets | `[-5.53, 3.2]` | `[-0.07, 0.04]` |
| excluded_bins | `[45, 46, 47, 48, 49]` | `[39, 40, 41, 42, 43]` |
| water_depth_m | `26.9` | `24.0` |

Station B has 49 bins (about 1.67–25.67 m). Station A has 43 bins (about 1.67–22.67 m).
The excluded bins are the uppermost, near-surface bins. Their valid-velocity fraction falls
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
| verdant_sheets | Sheet names corresponding to alphabetically sorted workbooks |
| verdant_heading_offsets | Matching heading corrections in degrees; Station B `[-5.53, 3.2]`, Station A `[-0.07, 0.04]` |
| excluded_bins | Integer bin IDs to exclude; Verdant Station B excludes 45–49, Station A 39–43 (see Verdant stations) |
| max_speed_mps | Maximum accepted horizontal speed, m/s |
| min_bin_coverage | Fraction of selected bins required for a valid depth average, (0,1] |
| water_depth_m | Total water depth at the ADCP in metres, or `null`. Known sites: Verdant Station A 24.0, Station B 26.9; CO-OPS LIS1016 37.8 (124 ft, [NOAA station page](https://tidesandcurrents.noaa.gov/noaacurrents/predictions.html?id=LIS1016_1)) |

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
