from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta

from .data import JST, drop_unclosed, fetch_bars, load_bars_csv
from .engine import M5, Signal, replay
from .notify import format_signal, send
from .pairs import pair_from_key, params_for
from .parser import ParseError, load_scenarios

DEFAULT_PAIR = "EURUSD"


def _since(v: str | None):
    if not v:
        return None
    d = datetime.fromisoformat(v.strip())
    return d.replace(tzinfo=JST) if d.tzinfo is None else d.astimezone(JST)


def git_since(path: str):
    """そのCSVを最後にコミットした時刻 = シナリオの有効開始時刻。"""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cI", "--", path],
                             capture_output=True, text=True, timeout=10).stdout.strip()
        return _since(out) if out else None
    except Exception:  # noqa: BLE001
        return None


def print_check(pair, scenarios) -> None:
    print(f"==== {pair.symbol} ====")
    if not scenarios:
        print("（シナリオ未登録）\n")
    for sc in scenarios:
        print(f"■ {sc.name}  [{'売り' if sc.side == 'short' else '買い'}]")
        for i, st in enumerate(sc.steps, 1):
            print(f"   {i}. {st.describe()}")
        print(f"   → エントリー目安 {sc.entry} / 損切り {sc.sl} / 利確1 {sc.tp1} / 利確2 {sc.tp2}\n")


def _params(pair):
    env = os.environ.get
    return params_for(pair, float(env("TOL_PIPS") or 3), float(env("MAX_ENTRY_DEVIATION_PIPS") or 8),
                      int(env("COOLDOWN_BARS") or 12))


def scan(path, pair, scenarios, notified: dict, now: datetime, a) -> bool:
    env = os.environ.get
    since = _since(a.since or env("SIGNAL_SINCE")) or git_since(path)
    bars = drop_unclosed(fetch_bars(env("TWELVE_DATA_API_KEY", ""), pair.symbol,
                                    int(env("LOOKBACK_BARS") or 288)), now)
    if not bars or now - (bars[-1].t + M5) > timedelta(minutes=30):
        print(f"[{pair.symbol}] 最新の確定足が古い（市場休場の可能性）。何もせず終了")
        return False
    max_age = timedelta(minutes=int(env("NOTIFY_MAX_AGE_MIN") or 30))
    changed = False
    for s in replay(scenarios, bars, _params(pair), since):
        key = f"{pair.symbol}|{s.scenario.name}|{s.t.isoformat()}"
        if key in notified or now - (s.t + M5) > max_age:
            continue
        msg = format_signal(s)
        print(msg, "\n")
        if a.dry_run:
            continue
        if send(msg):
            notified[key] = now.isoformat()
            changed = True
    return changed


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default="signals.csv", help="シナリオCSV（既定: リポジトリ直下の signals.csv）")
    ap.add_argument("--pair", help=f"通貨ペア（既定: 環境変数 PAIR、なければ {DEFAULT_PAIR}）")
    ap.add_argument("--check", action="store_true", help="CSVの解釈結果を表示して終了")
    ap.add_argument("--test-notify", action="store_true", help="テスト通知を1通送って終了")
    ap.add_argument("--bars-csv", help="ローカルの5分足CSVで全期間リプレイ（検証用。通知なし）")
    ap.add_argument("--dry-run", action="store_true", help="通知・状態保存をしない")
    ap.add_argument("--since", help="この時刻以降の足だけで判定（ISO。無印はJST）")
    ap.add_argument("--state", default=os.environ.get("STATE_PATH", "state/notified.json"))
    a = ap.parse_args(argv)
    env = os.environ.get

    try:
        pair = pair_from_key(a.pair or env("PAIR") or DEFAULT_PAIR)
        scenarios = load_scenarios(a.csv, pair.symbol)
    except FileNotFoundError:
        print(f"CSVが見つかりません: {a.csv}", file=sys.stderr)
        return 1
    except (ParseError, ValueError) as e:
        print(f"CSVエラー [{a.csv}]: {e}", file=sys.stderr)
        return 1

    if a.check:
        print_check(pair, scenarios)
        return 0

    if a.test_notify:
        if scenarios:
            sc = scenarios[0]
            msg = "【テスト通知】\n" + format_signal(Signal(sc, datetime.now(JST), sc.entry))
        else:
            msg = f"【テスト通知】\n{pair.symbol} 通知経路の確認（シナリオ未登録）"
        print(msg)
        if send(msg):
            return 0
        print("どの通知先にも送信できませんでした", file=sys.stderr)
        return 1

    if not scenarios:
        print(f"[{pair.symbol}] シナリオ未登録のためスキップ（APIは呼びません）")
        return 0

    if a.bars_csv:
        for s in replay(scenarios, load_bars_csv(a.bars_csv), _params(pair), _since(a.since or env("SIGNAL_SINCE"))):
            print(format_signal(s), "\n")
        return 0

    now = datetime.now(JST)
    try:
        with open(a.state, encoding="utf-8") as fh:
            notified = json.load(fh)
    except FileNotFoundError:
        notified = {}
    changed = scan(a.csv, pair, scenarios, notified, now, a)
    cutoff = now - timedelta(days=3)
    pruned = {k: v for k, v in notified.items() if datetime.fromisoformat(v) > cutoff}
    if (changed or pruned != notified) and not a.dry_run:
        os.makedirs(os.path.dirname(a.state) or ".", exist_ok=True)
        with open(a.state, "w", encoding="utf-8") as fh:
            json.dump(pruned, fh, ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
