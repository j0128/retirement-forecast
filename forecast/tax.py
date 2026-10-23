"""台灣綜合所得稅（個人）：級距、免稅額與扣除額，以所得年度（民國）為準。

數字來源：財政部公告 114 年度、115 年度綜合所得稅相關免稅額、扣除額、課稅級距。
後續年度若法令調整，可在 exe（或專案）旁放 `tax_tables.json` 覆寫 / 新增，格式見 README。
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from typing import Optional

INF = float("inf")


@dataclass(frozen=True)
class TaxTable:
    year: int                    # 民國年度（所得年度）
    exemption: float             # 免稅額（每人）
    exemption_70: float          # 70 歲以上免稅額
    std_single: float            # 標準扣除額（單身）
    std_married: float           # 標準扣除額（有配偶）
    salary_deduction: float      # 薪資所得特別扣除額（上限）
    brackets: tuple              # ((級距上限, 稅率 %), ...) 最後一級上限為 inf


BUILTIN = {
    114: TaxTable(114, 97_000, 145_500, 131_000, 262_000, 218_000,
                  ((590_000, 5), (1_330_000, 12), (2_660_000, 20), (4_980_000, 30), (INF, 40))),
    115: TaxTable(115, 101_000, 151_500, 136_000, 272_000, 227_000,
                  ((610_000, 5), (1_380_000, 12), (2_770_000, 20), (5_190_000, 30), (INF, 40))),
}
_tables = dict(BUILTIN)
RENT_COST_RATE = 0.43            # 租賃所得：必要損耗及費用（未舉證時）以收入的 43% 計


def load_overrides(path: str) -> int:
    """讀取 tax_tables.json 覆寫/新增年度表，回傳載入的年度數。檔案不存在或格式錯誤則忽略。"""
    global _tables
    _tables = dict(BUILTIN)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        for k, d in data.items():
            yr = int(k)
            br = tuple((INF if b[0] in (None, "inf") else float(b[0]), float(b[1])) for b in d["brackets"])
            _tables[yr] = TaxTable(yr, float(d["exemption"]), float(d["exemption_70"]), float(d["std_single"]),
                                   float(d["std_married"]), float(d["salary_deduction"]), br)
        return len(data)
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return 0


def table_for(roc_year: int, inflation_pct: float = 2.0, index: bool = True) -> TaxTable:
    """取得所得年度的稅率表。超過已公告年度時，可依通膨逐年調高（模擬法定隨 CPI 調整）。"""
    if roc_year in _tables:
        return _tables[roc_year]
    years = sorted(_tables)
    if roc_year < years[0]:
        return _tables[years[0]]
    base = _tables[years[-1]]
    if not index or roc_year <= base.year:
        return base
    f = (1 + inflation_pct / 100) ** (roc_year - base.year)
    return replace(base, year=roc_year, exemption=base.exemption * f, exemption_70=base.exemption_70 * f,
                   std_single=base.std_single * f, std_married=base.std_married * f,
                   salary_deduction=base.salary_deduction * f,
                   brackets=tuple((u * f if u != INF else INF, r) for u, r in base.brackets))


def progressive_tax(net: float, brackets: tuple) -> tuple:
    """回傳 (應納稅額, 邊際稅率 %)。"""
    tax, lower, marginal = 0.0, 0.0, brackets[0][1]
    for upper, rate in brackets:
        if net > lower:
            tax += (min(net, upper) - lower) * rate / 100
            marginal = rate
        lower = upper
    return tax, marginal


def income_tax(table: TaxTable, *, salary: float = 0.0, rent: float = 0.0, other: float = 0.0,
               married: bool = False, dependents: float = 0, elders: float = 0, taxpayer_70: bool = False,
               itemized: float = 0.0, other_deduction: float = 0.0) -> dict:
    """計算一年度綜合所得稅。
    salary 薪資所得（受薪、兼職）；rent 租金收入（扣 43% 必要費用）；other 其他全額課稅所得。
    dependents 扶養親屬人數（不含 70 歲以上）；elders 其中 70 歲以上扶養人數。
    不含：基本稅額（AMT）、基本生活費差額、股利/利息分離課稅等特殊規定。"""
    rent_net = rent * (1 - RENT_COST_RATE)
    gross = salary + rent_net + other
    self_ex = table.exemption_70 if taxpayer_70 else table.exemption
    exemptions = self_ex + (table.exemption if married else 0.0) + dependents * table.exemption \
        + elders * table.exemption_70
    std = table.std_married if married else table.std_single
    deduction = max(std, itemized)
    salary_ded = min(salary, table.salary_deduction)
    net = max(0.0, gross - exemptions - deduction - salary_ded - other_deduction)
    tax, marginal = progressive_tax(net, table.brackets)
    return {"year": table.year, "gross": gross, "salary": salary, "rent_net": rent_net, "other": other,
            "exemptions": exemptions, "deduction": deduction, "salary_deduction": salary_ded,
            "other_deduction": other_deduction, "net_income": net, "tax": tax, "marginal": marginal,
            "effective": (tax / (salary + rent + other)) if (salary + rent + other) > 0 else 0.0}
