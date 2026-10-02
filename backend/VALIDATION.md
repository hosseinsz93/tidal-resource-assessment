# Consolidation validation — 29 September 2026

Latest JSON-configuration revision: 29 tests pass, including example loading, inline curve
points, invalid types, unknown/duplicate keys and cut-in/slack conflicts. Complete CO-OPS
and Verdant notebook executions passed using their respective `inputs/config/*.json` files.
The only subsequent notebook edit clarified `null` water depth in explanatory Markdown.
The previous widget-based checks below document earlier revisions; setup now uses JSON.

- 21 numerical/adapter regression tests passed (`python -m pytest backend/tests`), including restored fixed-period amplitude/phase, original TI denominator/noise correction, peak-profile exponent, operating duration, signed PDF/CDF normalization, editable/generated turbine curves, threshold propagation and notebook cut-in/slack synchronization.
- The main notebook passed schema validation and execution of every code cell with the supplied CO-OPS data.
- The same notebook passed execution after selecting Verdant through its source control, including the visible 45–49 bin exclusion preset.
- Both executions exercised preprocessing, shared analyses, CSV/run-log export, figure generation and creation of the interactive exploration controls.
- Both sources were executed again with the restored original postprocessing, result-table browser, 21-entry postprocessing checklist and figure gallery. The final notebook edit after execution changed explanatory Markdown only.
- Restored CO-OPS peak-power/flow-summary and Verdant event/log-profile figures were visually inspected for readable labels, legends and coordinate qualifications.
- Subsequent turbine-control and signed-profile changes passed complete CO-OPS and Verdant notebook executions. The exported peak-profile plot was visually checked: negative ebb is on the left, positive flood on the right.
- Selected CO-OPS statistics/current-rose/profile figures and Verdant profile-fit figures were visually inspected. Model-fit lines use neutral colors to preserve red=flood and blue=ebb.
- There is exactly one notebook at the repository root.

Regression cases cover unit conversion, heading rotation, true bed geometry, arbitrary CO-OPS segment counts, overlapping records, missing-bin handling, shared phase labels, synthetic harmonic/power/log fits, gap-aware duration weights across pandas timestamp precisions, energy cutoffs/normalization, settings snapshots, notebook presets and saved-setting restoration.

Testing used an isolated Python 3.12 environment with pandas, NumPy, Matplotlib, openpyxl and Jupyter dependencies. The pre-existing local Conda environment could not be launched from this session; it was not modified. The repository's environment file and setup instructions include the new notebook dependencies.

Completed example runs are retained under matching folders in `outputs/csv/` and `outputs/figures/`. Run logs (`run_log.json`) contain exact dependency versions, settings and hashes. These are workflow integration checks, not independent validation of site resource estimates or IEC compliance. Physical log-law fits remain unestimated with default unknown water depth; CO-OPS physical profile fits also await confirmation of its depth datum.
