# Backend modules

`config.py` defines settings (copied at preprocessing) and the dataset wrapper. `settings_file.py` loads and validates the user JSON configuration. `loaders.py` contains source adapters and shared validation. `analysis.py` operates on named canonical columns. `workflow.py` orchestrates the three stages and provenance. `plots.py` renders summaries; `notebook.py` provides result exploration and retains the older optional setup panel for compatibility. The main notebook uses JSON only for setup.

An adapter returns a `Dataset` with `time, bin, depth_m, depth_reference, east_mps, north_mps, source_file`, metadata, messages, and input paths. Register a new adapter in `loaders.load`, then add settings/UI fields. No analysis function should inspect source-file positions or instrument-specific units.

All phases use the same flood-oriented axis; resolved rows inherit exact-time labels instead of reclassifying at a representative bin. Depth averages require a configurable fraction of retained bins. Smoothing and rolling windows split at gaps and missing velocity runs.

`time_support` uses timedeltas in seconds, independent of pandas timestamp precision. It assigns forward support to ensemble-start samples, caps gaps at nominal cadence, and gives the last sample one nominal interval. This convention controls phase durations and energy probabilities. Cycle endpoints use interpolated zero-crossing times within uninterrupted blocks.

Physical power/log fits use phase-mean along-channel magnitudes at confirmed bed heights. Peak profiles are exported separately. Power fitting uses log u vs log z; log fitting uses u vs log z over the configured z/h range. R² uses residuals in velocity space. No p-value is fabricated from correlated samples. Missing metadata or insufficient near-bed points produce explicit fit statuses.

Residual intensity uses sample standard deviation of rolling residuals divided by mean absolute along velocity at eligible times. It is sample-weighted within a phase, unlike duration-weighted energy. Noise subtraction defaults to zero; negative corrected variance is clipped with a flag. These ensemble-level statistics are not validated estimates of full turbulence intensity.

Energy supports one hub bin, one turbine curve, availability and gross turbine-count scaling. Rotor-area averaging, harmonic annual reconstruction, uncertainty propagation, wakes and turbine loads are future extensions, not implicit features.
