# Original postprocessing in the single notebook

Run Preprocess → Process → Postprocess in `Tidal_Resource_Assessment.ipynb`.
The result-table selector exposes every table; the saved-figure selector exposes every figure.
The exported `postprocessing_catalog.csv` maps original analyses to their new outputs and
indicates unavailable or disabled optional analyses. All calculations remain in the backend.

| Original workflow | Retained postprocessing |
| --- | --- |
| flowVisualized.py | All six views: mean speeds/direction compass, signed time series, components, phase histograms/box plots, current rose, tidal series/histogram |
| principal_flood_ebb_calculation.ipynb | Axis and covariance ellipse, signed PDF/CDF, dominant bearings, profile/depth-mean peaks, per-bin peaks, hours/percent above cut-in |
| tidal-cycles.ipynb | Global/phase/event PCU, event duration/RMS/peaks, normalized cycles with zero-offset cosine and Pearson statistics, cosine view, single-peak power fits with alpha/beta/U, event profiles, normalized phase-mean log fits and friction parameters |
| TI-calculator.ipynb | Original rolling horizontal-speed denominator, raw and noise-corrected TI by bin, pooled across depth, and for the depth-averaged record; profile and phase-comparison plots |
| adcp_aep_pcu_iec.ipynb | Power curve, hub probabilities, per-speed-bin AEP, unconditional signed flood/ebb probabilities, turbine/farm annual and observed-period energy, period-scaled annual estimate |
| orientation-correction.ipynb | Deployment/combined circular and arithmetic directions, configured offsets, before/after axis comparison, phase bearings and separate ebb/flood polar plots |
| coops-data.ipynb | Optional annual prediction-event tables, station time series; normalized-cycle and cosine-fit tables (no figure) |
| MATLAB / inputs02 cosine prototypes | Full-record 12 h 25 min harmonic, amplitude/phase, fit statistics, observed/fitted series and residuals |

## Definitions and explicit differences

- Original normalized profile fits are retained **separately** from physically referenced fits.
  Legacy mode infers coordinate orientation from velocity and uses the original rank or
  min/max depth normalization. Its inferred coordinates and roughness fraction must not be
  interpreted as measured bed geometry. Physical mode requires confirmed height and depth.
- Original TI uses phase-filtered rolling along-velocity residuals divided by rolling horizontal
  speed. The newer residual-intensity tables remain separate. Both respect data gaps.
  Noise is a user setting (default zero), not an assumed universal instrument constant.
- Signed hub probabilities include near-slack samples according to sign, independently of
  the threshold-based phase classification used elsewhere.
- Annual files contain nonuniform prediction events. Their interpolated cycle comparisons
  are separate diagnostics, never substituted for measured ADCP distributions or energy input.
- Orientation comparisons use the selected, validated bins. Configured corrections are
  reported, not automatically estimated again from circular means.
- Fit Pearson p-values are retained as descriptive legacy outputs; their independence
  assumption is generally unsuitable for autocorrelated/interpolated tidal samples.
- The fixed-period fit uses deterministic least squares for the original model instead of
  the prototype optimizer's fallback guesses. It is not long-term harmonic prediction.
- Shared units, vector means, phase labels, gap handling, and named columns replace inconsistent
  legacy conventions. Preservation concerns analyses and outputs, not reproducing known bugs.

An unavailable phase, insufficient fit coordinates, disabled energy, or absent optional input
is reported rather than filled with fabricated results. Archived originals remain unchanged.
