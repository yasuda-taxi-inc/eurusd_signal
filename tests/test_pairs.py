import contextlib
import io
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest import mock

from scanner import main as M
from scanner.data import JST
from scanner.engine import Bar, replay
from scanner.notify import format_signal
from scanner.pairs import pair_from_key, params_for
from scanner.parser import load_scenarios

HEADER = '"シナリオ","エントリー方針・想定価格","第一利確","第二利確","損切り"\n'
EURUSD_CSV = HEADER + (
    '"ロング・押し目","1.1700前後で安値更新に失敗し、1.1710回復後の押しを維持。1.1710付近で買い","1.1725","1.1740","1.1692"\n'
)
ROWS = [(1.1708, 1.1709, 1.1702, 1.1705), (1.1705, 1.1713, 1.1704, 1.1712), (1.1712, 1.1714, 1.1711, 1.1711)]


def write_csv(d, text):
    path = os.path.join(d, "signals.csv")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def run_main(args, bars=None, side_effect=None):
    buf = io.StringIO()
    kw = {"side_effect": side_effect} if side_effect else {"return_value": bars}
    with mock.patch.object(M, "fetch_bars", **kw), contextlib.redirect_stdout(buf), \
            contextlib.redirect_stderr(io.StringIO()):
        rc = M.main(args)
    return rc, buf.getvalue()


class P(unittest.TestCase):
    def test_pair_from_key(self):
        self.assertEqual(pair_from_key("EURUSD").symbol, "EUR/USD")
        self.assertEqual(pair_from_key("eur/usd").pip, 0.0001)
        with self.assertRaises(ValueError):
            pair_from_key("XXXYYY")

    def test_eurusd_pip_scaling_and_format(self):
        pair = pair_from_key("EURUSD")
        with tempfile.TemporaryDirectory() as d:
            scs = load_scenarios(write_csv(d, EURUSD_CSV), pair.symbol)
        t0 = datetime(2026, 10, 5, 16, 0, tzinfo=JST)
        bars = [Bar(t0 + timedelta(minutes=5 * i), *r) for i, r in enumerate(ROWS)]
        sigs = replay(scs, bars, params_for(pair))
        self.assertEqual(len(sigs), 1)
        msg = format_signal(sigs[0])
        self.assertIn("EUR/USD シグナル", msg)
        self.assertIn("エントリー目安：1.17100", msg)
        self.assertIn("-18.0pips", msg)   # 1.1710 → 1.1692
        self.assertIn("+15.0pips", msg)   # 1.1710 → 1.1725
        self.assertAlmostEqual(params_for(pair).tol, 0.0003)

    def test_main_live_dry_run(self):
        now = datetime.now(JST)
        last_open = (now - timedelta(minutes=5)).replace(second=0, microsecond=0)
        last_open -= timedelta(minutes=last_open.minute % 5)
        start = last_open - timedelta(minutes=10)
        bars = [Bar(start + timedelta(minutes=5 * i), *r) for i, r in enumerate(ROWS)]
        with tempfile.TemporaryDirectory() as d:
            path = write_csv(d, EURUSD_CSV)
            rc, out = run_main(["--csv", path, "--dry-run", "--state", os.path.join(d, "s.json")], bars)
        self.assertEqual(rc, 0)
        self.assertIn("EUR/USD シグナル", out)

    def test_header_only_csv_is_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            path = write_csv(d, HEADER)
            rc, out = run_main(["--csv", path, "--dry-run"], side_effect=AssertionError("APIを呼ばないはず"))
        self.assertEqual(rc, 0)
        self.assertIn("スキップ", out)

    def test_broken_csv_returns_error(self):
        with tempfile.TemporaryDirectory() as d:
            rc, _ = run_main(["--csv", write_csv(d, "壊れたCSV\n"), "--dry-run"], side_effect=AssertionError)
        self.assertEqual(rc, 1)

    def test_missing_csv_returns_error(self):
        rc, _ = run_main(["--csv", "/nonexistent/signals.csv"], side_effect=AssertionError)
        self.assertEqual(rc, 1)

    def test_shipped_template_is_empty_and_valid(self):
        self.assertEqual(load_scenarios("signals.csv", "EUR/USD"), [])


if __name__ == "__main__":
    unittest.main()
