# Assignment: Telecom KPI Analyzer

## Goal
Analyze simulated 4G/5G cell measurements and explain performance warnings.

## Technology
Python 3.10+, SQLite. No pip installation required.

## Tasks
1. Run `python analyzer.py --out output` and open `output/report.html`.
2. Explain why CELL_B has four warnings: call drop rate about 6.30%, average latency 85 ms, throughput about 4.67 Mbps, and peak utilization 96%.
3. Calculate call drop rate manually: `100 * 17 / 270`. Explain why the denominator is established calls.
4. Explain why CELL_D shows N/A for call drop rate instead of 0%.
5. Add a new synthetic cell to a copy of `sample_kpis.csv`, then analyze it using `--csv your_sample.csv`.
6. Change one threshold using `--drop`, `--latency`, `--throughput`, or `--utilization`. Explain how the warning rule changed.
7. Run `python -m unittest discover -s tests -v`.

## Show in your demonstration
- CSV input and the validation rules.
- SQL GROUP BY, SUM, AVG, MAX, and NULLIF.
- Generated HTML, CSV, JSON, and SQLite output.
- A manual calculation matching the report and one test rejecting invalid data.

## Explain these points
- Sum call counters before dividing; do not average percentages from different call volumes.
- Download MB means decimal megabytes; multiply by eight and divide by seconds for Mbps.
- Latency here is an equally weighted mean of interval values.
- Sample thresholds are learning choices, not operator SLAs.
- Alarms flag symptoms and do not establish a root cause.

## Validation note
The ten KPI tests passed in the original environment. The input is simulated and the program does not access a live operator network.
