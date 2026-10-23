# Telecom KPI Analyzer

**Python + SQLite | Data analysis, KPIs, SQL, reporting**

Reads a small CSV of **simulated** cell measurements, validates it, groups counters using SQL, and creates cell-level reports with performance alarms. No live mobile network access or third-party dependencies.

```powershell
# Run from this project folder
python analyzer.py --out output
Start-Process output/report.html
```

## Data and calculations

Each row is one non-overlapping measurement interval for a cell and technology. Call counters are events occurring during that interval, not cumulative counters. Latency is one representative interval measurement. Download MB and transfer seconds refer to the same observed transfer. MB means decimal megabytes.

| Metric | Calculation | Demo warning |
| --- | --- | --- |
| Call drop rate | 100 x SUM(dropped calls) / SUM(established calls) | > 2% |
| Call setup success | 100 x SUM(established calls) / SUM(call attempts) | Reported in CSV/JSON; no alarm |
| Average latency | Arithmetic mean of interval latency measurements | > 50 ms |
| Throughput | 8 x SUM(download MB) / SUM(transfer seconds) | < 10 Mbps |
| Peak utilization | MAX(interval utilization %) | > 85% |

These thresholds are demonstration choices, not operator standards. Throughput is the observed transfer rate, not the theoretical capacity of 4G or 5G. The latency average gives each row equal weight; this is not a packet-weighted average. High utilization is a possible congestion symptom, not proof of the cause.

**Do not average call drop percentages.** If one interval has 5 drops from 10 established calls and another has 0 from 1000, the combined rate is `100 * 5 / 1010`, approximately 0.495%, not 25%.

No established calls means call drop rate is **N/A**, not zero. The sample CELL_D demonstrates this case.

## Expected sample results

| Cell | Type | Call drop % | Avg latency ms | Throughput Mbps | Alarms |
| --- | --- | --- | --- | --- | --- |
| CELL_A | 4G | 0.93 | 27.5 | 22.00 | None |
| CELL_B | 4G | 6.30 | 85.0 | 4.67 | High call drop, high latency, low throughput, high utilization |
| CELL_C | 5G | 0.57 | 13.5 | 110.00 | None |
| CELL_D | 5G | N/A | 21.0 | 14.00 | None; no established calls |

## Try a change

```powershell
python analyzer.py --drop 7 --latency 100 --throughput 4 --utilization 99 --out changed-output
```

CELL_B no longer triggers these demo thresholds. That changes the alert policy, not the network data or network quality.

## Validation

Rejects missing/wrong headers, empty data, invalid timestamps, unknown technology, negative or non-finite measurements, duplicate cell/time/type observations, impossible call counts, zero transfer duration, and utilization above 100%.

Outputs are `cell_summary.csv`, `summary.json`, `report.html`, and `measurements.sqlite`. A rerun replaces the output snapshot; it does not accumulate repeated intervals.

```sql
SELECT cell_id,
       SUM(dropped_calls) AS drops,
       SUM(established_calls) AS established,
       100.0 * SUM(dropped_calls) / NULLIF(SUM(established_calls), 0) AS drop_pct
FROM samples
GROUP BY cell_id;
```

## Limitations

This is a learning dataset, not a standardized vendor counter export. It does not include RF signal measurements, handover analysis, packet capture, or integration with NetAct/SolarWinds. Alarms identify symptoms; further inspection is needed before changing network settings.


## Practice assignment and tests

Read [ASSIGNMENT.md](ASSIGNMENT.md) for the demonstration and exercises.

```powershell
python -m unittest discover -s tests -v
```

This is an educational personal project. AI assistance was used in preparing the initial implementation. Practise the code and demonstrations before presenting it in an interview. Simulated data is explicitly labeled in reports.

References: [Python sockets](https://docs.python.org/3/library/socket.html), [SQLite](https://docs.python.org/3/library/sqlite3.html), [unittest](https://docs.python.org/3/library/unittest.html).
