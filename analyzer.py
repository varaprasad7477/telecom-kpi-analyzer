"""Analyze simulated telecom counters using Python and SQLite. No pip installs."""
import argparse
from contextlib import closing
import csv
from datetime import datetime
import html
import json
import math
from pathlib import Path
import sqlite3

FIELDS = ['timestamp','cell_id','technology','call_attempts','established_calls',
          'dropped_calls','latency_ms','download_mb','transfer_seconds','utilization_pct']


def load_rows(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != FIELDS:
            raise ValueError('CSV columns must match: ' + ','.join(FIELDS))
        rows = list(reader)
    if not rows:
        raise ValueError('CSV contains no measurements')
    seen = set()
    for number, row in enumerate(rows, 2):
        try:
            if None in row or any(value is None for value in row.values()):
                raise ValueError('Each row must have exactly the expected number of columns')
            datetime.fromisoformat(row['timestamp'])
            if not row['cell_id'].strip() or row['technology'] not in {'4G', '5G'}:
                raise ValueError('Cell ID is required and technology must be 4G or 5G')
            for name in FIELDS[3:]:
                row[name] = int(row[name]) if name in FIELDS[3:6] else float(row[name])
                if not math.isfinite(row[name]) or row[name] < 0:
                    raise ValueError('Counters must be finite and non-negative')
            if not row['dropped_calls'] <= row['established_calls'] <= row['call_attempts']:
                raise ValueError('Require dropped <= established <= attempted calls')
            if row['transfer_seconds'] <= 0 or row['utilization_pct'] > 100:
                raise ValueError('Transfer duration must be positive; utilization must be <= 100')
            key = (row['timestamp'], row['cell_id'], row['technology'])
            if key in seen:
                raise ValueError('Duplicate cell/time/technology measurement')
            seen.add(key)
        except (ValueError, TypeError) as exc:
            raise ValueError(f'Row {number}: {exc}') from exc
    return rows


def calculate(rows):
    """Aggregate COUNTERS before dividing; never average per-interval percentages."""
    with closing(sqlite3.connect(':memory:')) as db, db:
        db.row_factory = sqlite3.Row
        db.execute('''CREATE TABLE samples(timestamp TEXT,cell_id TEXT,technology TEXT,
            call_attempts INTEGER,established_calls INTEGER,dropped_calls INTEGER,
            latency_ms REAL,download_mb REAL,transfer_seconds REAL,utilization_pct REAL)''')
        db.executemany('INSERT INTO samples VALUES (?,?,?,?,?,?,?,?,?,?)',
                       [tuple(r[f] for f in FIELDS) for r in rows])
        results = [dict(r) for r in db.execute('''SELECT cell_id, technology,
            COUNT(*) AS intervals, SUM(call_attempts) AS call_attempts,
            SUM(established_calls) AS established_calls, SUM(dropped_calls) AS dropped_calls,
            100.0 * SUM(dropped_calls) / NULLIF(SUM(established_calls),0) AS call_drop_pct,
            100.0 * SUM(established_calls) / NULLIF(SUM(call_attempts),0) AS setup_success_pct,
            AVG(latency_ms) AS avg_latency_ms,
            8.0 * SUM(download_mb) / SUM(transfer_seconds) AS throughput_mbps,
            MAX(utilization_pct) AS peak_utilization_pct
            FROM samples GROUP BY cell_id, technology ORDER BY cell_id, technology''')]
    return results


def alarms(row, thresholds):
    flags = []
    if row['call_drop_pct'] is not None and row['call_drop_pct'] > thresholds['drop']:
        flags.append('HIGH_CALL_DROP')
    if row['avg_latency_ms'] > thresholds['latency']:
        flags.append('HIGH_LATENCY')
    if row['throughput_mbps'] < thresholds['throughput']:
        flags.append('LOW_THROUGHPUT')
    if row['peak_utilization_pct'] > thresholds['utilization']:
        flags.append('HIGH_UTILIZATION')
    return flags


def analyze(path, out, thresholds):
    rows = load_rows(path)
    results = calculate(rows)
    for row in results:
        row['alarms'] = '; '.join(alarms(row, thresholds)) or 'NONE'
        row['data_note'] = 'No established calls' if row['call_drop_pct'] is None else ''
    directory = Path(out)
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / 'cell_summary.csv').open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(results)
    (directory / 'summary.json').write_text(json.dumps(dict(data_source='simulated educational data',
        thresholds=thresholds, measurement_count=len(rows), cells=results), indent=2), encoding='utf-8')
    # Preserve validated interval data in SQLite for simple SELECT/GROUP BY practice.
    with closing(sqlite3.connect(directory / 'measurements.sqlite')) as db, db:
        db.execute('DROP TABLE IF EXISTS samples')
        db.execute('''CREATE TABLE samples(timestamp TEXT,cell_id TEXT,technology TEXT,
            call_attempts INTEGER,established_calls INTEGER,dropped_calls INTEGER,
            latency_ms REAL,download_mb REAL,transfer_seconds REAL,utilization_pct REAL)''')
        db.executemany('INSERT INTO samples VALUES (?,?,?,?,?,?,?,?,?,?)',
                       [tuple(r[f] for f in FIELDS) for r in rows])
    display_fields = ['cell_id','technology','call_drop_pct','avg_latency_ms',
                      'throughput_mbps','peak_utilization_pct','alarms','data_note']
    def display(value):
        if value is None:
            return 'N/A'
        return f'{value:.2f}' if isinstance(value, float) else str(value)
    table = ''.join('<tr>' + ''.join('<td>' + html.escape(display(r[k])) + '</td>'
                    for k in display_fields) + '</tr>' for r in results)
    bars = ''
    for index, row in enumerate(results):
        width = min(100, row['call_drop_pct'] or 0) * 5
        y = 25 + index * 43
        bars += f'<text x="0" y="{y+14}">{html.escape(row["cell_id"])}</text><rect x="110" y="{y}" width="{width:.2f}" height="20" fill="#167c91"/><text x="{120+width:.2f}" y="{y+14}">{display(row["call_drop_pct"])}%</text>'
    alert_cells = sum(r['alarms'] != 'NONE' for r in results)
    heads = ['Cell','Type','Call drop %','Average latency ms','Throughput Mbps','Peak use %','Alarms','Data note']
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Telecom KPI Analyzer</title><style>body{{font:16px system-ui;color:#182d3b;background:#f4f7fa;margin:40px auto;max-width:1200px;padding:0 22px}}h1{{font-size:32px}}.note{{background:#fff4da;padding:14px;border-radius:8px}}.cards{{display:flex;gap:20px;flex-wrap:wrap}}.card{{background:white;border:1px solid #dbe4eb;border-radius:10px;padding:20px;min-width:130px}}strong{{display:block;font-size:28px}}table{{border-collapse:collapse;width:100%;background:white}}td,th{{padding:12px;border-bottom:1px solid #dbe4eb;text-align:left}}.table{{overflow:auto}}svg{{background:white;max-width:100%;height:auto}}code{{background:#e5ebf0;padding:3px}}</style>
    <h1>Telecom KPI Analyzer</h1><p class="note">SIMULATED EDUCATIONAL DATA | No connection to a live 4G/5G operator network.</p>
    <div class="cards"><div class="card">Measurements<strong>{len(rows)}</strong></div><div class="card">Cells<strong>{len(results)}</strong></div><div class="card">Cells with alarms<strong>{alert_cells}</strong></div></div>
    <h2>Cell performance</h2><div class="table"><table><thead><tr>{''.join('<th>'+v+'</th>' for v in heads)}</tr></thead><tbody>{table}</tbody></table></div>
    <h2>Call drop rate</h2><p>Bars use the same scale: 5 pixels per percentage point. N/A means no established calls.</p>
    <svg viewBox="0 0 750 {50+len(results)*43}" role="img" aria-label="Call drop rate per cell">{bars}</svg>
    <h2>How it is calculated</h2><p>Call drop % = 100 x dropped calls / established calls.<br>
    Setup success % = 100 x established calls / call attempts.<br>
    Throughput Mbps = 8 x total download MB / total transfer seconds (decimal MB).<br>
    Latency = arithmetic mean of interval latency measurements. Peak use = highest interval utilization.</p>
    <p>Demo thresholds: call drop &gt; {thresholds['drop']:g}%; latency &gt; {thresholds['latency']:g} ms; throughput &lt; {thresholds['throughput']:g} Mbps; peak use &gt; {thresholds['utilization']:g}%.</p>
    <p>Thresholds are learning examples, not operator SLAs. Alarms flag symptoms for investigation; they do not prove root cause or RF congestion.</p></html>'''
    (directory / 'report.html').write_text(page, encoding='utf-8')
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', default=str(Path(__file__).with_name('sample_kpis.csv')))
    parser.add_argument('--out', default='output')
    parser.add_argument('--drop', type=float, default=2)
    parser.add_argument('--latency', type=float, default=50)
    parser.add_argument('--throughput', type=float, default=10)
    parser.add_argument('--utilization', type=float, default=85)
    args = parser.parse_args(argv)
    thresholds = {k: getattr(args, k) for k in ('drop','latency','throughput','utilization')}
    if any(not math.isfinite(v) or v < 0 for v in thresholds.values()) or args.drop > 100 or args.utilization > 100:
        parser.error('Thresholds must be finite, non-negative; percentages must be <= 100')
    try:
        results = analyze(args.csv, args.out, thresholds)
    except (ValueError, OSError, sqlite3.Error) as exc:
        parser.exit(1, f'Cannot analyze data: {exc}\n')
    for row in results:
        print(row['cell_id'], row['technology'], row['alarms'])
    print(f'Report: {Path(args.out).resolve() / "report.html"}')


if __name__ == '__main__':
    main()
