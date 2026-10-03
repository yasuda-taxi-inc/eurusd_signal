"""通貨ペアごとの設定。使うペアは環境変数 PAIR（既定 EURUSD）または --pair で指定する。"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .engine import Params


@dataclass(frozen=True)
class Pair:
    symbol: str   # Twelve Data のシンボル
    pip: float    # 1pip の価格幅
    digits: int   # 表示桁数


PAIRS = {
    "USDJPY": Pair("USD/JPY", 0.01, 3),
    "EURJPY": Pair("EUR/JPY", 0.01, 3),
    "EURUSD": Pair("EUR/USD", 0.0001, 5),
}


def by_symbol(symbol: str) -> Pair:
    for p in PAIRS.values():
        if p.symbol == symbol:
            return p
    raise ValueError(f"未対応の通貨ペア: {symbol}")


def pair_from_key(key: str) -> Pair:
    """'EURUSD' / 'eur/usd' / 'EUR_USD' などからペアを決める。"""
    k = re.sub(r"[^A-Za-z]", "", key).upper()
    if k not in PAIRS:
        raise ValueError(f"未対応の通貨ペア「{key}」（対応: {', '.join(PAIRS)}）")
    return PAIRS[k]


def params_for(pair: Pair, tol_pips: float = 3.0, max_dev_pips: float = 8.0, cooldown_bars: int = 12) -> Params:
    """pips指定の許容幅を、そのペアの価格幅に直す。"""
    return Params(tol=tol_pips * pair.pip, max_dev=max_dev_pips * pair.pip, cooldown_bars=cooldown_bars)
