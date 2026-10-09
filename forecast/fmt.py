"""數字格式與座標刻度工具（GUI 與報告共用）。"""
from __future__ import annotations

import math


def money(v: float) -> str:
    return f"{v:,.0f}"


def short_money(v: float) -> str:
    a = abs(v)
    if a >= 1e8:
        return f"{v / 1e8:,.2f}億"
    if a >= 1e4:
        return f"{v / 1e4:,.0f}萬"
    return f"{v:,.0f}"


def nice_ticks(lo: float, hi: float, n: int = 5) -> list:
    if hi <= lo:
        hi = lo + 1
    raw = (hi - lo) / n
    mag = 10 ** math.floor(math.log10(raw))
    step = min((m * mag for m in (1, 2, 2.5, 5, 10) if m * mag >= raw), default=raw)
    start = math.floor(lo / step) * step
    out, v = [], start
    while v <= hi + step * 0.5:
        out.append(v)
        v += step
    return out


def num_str(v: float) -> str:
    """輸入框用的數字字串：不使用科學記號，避免大數字被截成 6 位有效數字。"""
    v = float(v)
    return str(int(v)) if v == int(v) else f"{v:.10g}"
