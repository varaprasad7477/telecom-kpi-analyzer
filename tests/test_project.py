import importlib.util
from contextlib import closing
import json
from pathlib import Path
import socket
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

kpi = load('analyzer', ROOT / 'analyzer.py')
THRESHOLDS = dict(drop=2, latency=50, throughput=10, utilization=85)


class KpiTests(unittest.TestCase):
    def setUp(self):
        self.rows = kpi.load_rows(ROOT/'sample_kpis.csv')

    def test_expected_demo_alarm_cell(self):
        results = {r['cell_id']:r for r in kpi.calculate(self.rows)}
        self.assertEqual(len(kpi.alarms(results['CELL_B'], THRESHOLDS)),4)
        self.assertEqual(kpi.alarms(results['CELL_A'], THRESHOLDS),[])
        self.assertEqual(kpi.alarms(results['CELL_C'], THRESHOLDS),[])
        self.assertAlmostEqual(results['CELL_B']['call_drop_pct'],100*17/270)
        self.assertAlmostEqual(results['CELL_B']['throughput_mbps'],8*70/120)

    def test_aggregate_counts_before_ratios(self):
        first, second = self.rows[0].copy(), self.rows[1].copy()
        first.update(call_attempts=10, established_calls=10, dropped_calls=5)
        second.update(call_attempts=1000, established_calls=1000, dropped_calls=0)
        row = kpi.calculate([first,second])[0]
        self.assertAlmostEqual(row['call_drop_pct'],500/1010)
        self.assertNotEqual(row['call_drop_pct'],25)

    def test_zero_denominator_is_unknown(self):
        row = next(r for r in kpi.calculate(self.rows) if r['cell_id']=='CELL_D')
        self.assertIsNone(row['call_drop_pct'])
        self.assertIsNone(row['setup_success_pct'])

    def invalid_csv(self, transform):
        text = (ROOT/'sample_kpis.csv').read_text()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'invalid.csv'
            path.write_text(transform(text))
            with self.assertRaises(ValueError):
                kpi.load_rows(path)

    def test_inconsistent_counters_rejected(self):
        self.invalid_csv(lambda s:s.replace(',100,98,1,',',100,98,99,',1))

    def test_duplicate_interval_rejected(self):
        self.invalid_csv(lambda s:s+'\n'+s.splitlines()[1])

    def test_nan_rejected(self):
        self.invalid_csv(lambda s:s.replace(',25,150,',',nan,150,',1))

    def test_zero_transfer_duration_rejected(self):
        self.invalid_csv(lambda s:s.replace(',150,60,',',150,0,',1))

    def test_empty_input_rejected(self):
        self.invalid_csv(lambda s:s.splitlines()[0]+'\n')

    def test_report_and_sql_outputs(self):
        with tempfile.TemporaryDirectory() as temp:
            result = kpi.analyze(ROOT/'sample_kpis.csv',temp,THRESHOLDS)
            self.assertEqual(len(result),4)
            page = (Path(temp)/'report.html').read_text()
            self.assertIn('SIMULATED EDUCATIONAL DATA',page)
            self.assertIn('No established calls',page)
            with closing(sqlite3.connect(Path(temp)/'measurements.sqlite')) as db:
                self.assertEqual(db.execute('SELECT SUM(dropped_calls) FROM samples WHERE cell_id=?',('CELL_B',)).fetchone()[0],17)

    def test_exact_threshold_is_not_alarm(self):
        row = dict(call_drop_pct=2,avg_latency_ms=50,throughput_mbps=10,peak_utilization_pct=85)
        self.assertEqual(kpi.alarms(row,THRESHOLDS),[])

if __name__ == '__main__':
    unittest.main()
