"""退休收益預測引擎（純 Python，不依賴 GUI）。以「月」為單位模擬，名目金額（NT$）。"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, asdict
from typing import Optional

LABOR_PENSION_WAGE_CAP = 150_000  # 勞退提繳工資上限


@dataclass
class Account:
    name: str = "投資帳戶"
    cash: float = 0.0            # 目前現金/本金
    monthly_add: float = 0.0     # 每月增額
    annual_return: float = 5.0   # 預期年均報酬率 %
    years: float = 20.0          # 投資(加碼)年限；期滿後停止加碼但持續複利


@dataclass
class Loan:
    name: str = "房貸"
    mode: str = "fixed"          # fixed: 固定月扣款 / amort: 本息平均攤還
    monthly_payment: float = 0.0  # fixed 模式
    principal: float = 0.0        # amort 模式：原貸款金額
    annual_rate: float = 2.0      # amort 模式：年利率 %
    start: str = ""               # "YYYY-MM"
    end: str = ""                 # "YYYY-MM"（含）；amort 模式以年限推算時可留空
    years: float = 0.0            # amort 模式：貸款年限（end 空白時使用）


@dataclass
class Settings:
    current_age: float = 35
    retire_age: float = 65
    life_expectancy: float = 90
    monthly_income: float = 60_000      # 稅前月均收入
    income_growth: float = 2.0          # 每年調薪 %
    income_tax_rate: float = 5.0        # 所得稅有效稅率 %
    monthly_expense: float = 30_000     # 目前每月生活支出（今日幣值）
    retire_expense: float = 30_000      # 退休後每月生活支出（今日幣值）
    inflation: float = 2.0              # 通膨率 %
    gains_tax_rate: float = 0.0         # 投資獲利稅率 %
    savings_cash: float = 0.0           # 活存/未投入現金
    savings_rate: float = 1.0           # 活存年利率 %
    # 勞退新制
    lp_enabled: bool = True
    lp_wage: float = 0.0                # 提繳工資；0 = 取月收入（上限 150,000）
    lp_employer_pct: float = 6.0
    lp_self_pct: float = 0.0            # 自提 0~6%
    lp_balance: float = 0.0             # 帳戶現有餘額
    lp_return: float = 3.0              # 帳戶年收益率 %
    lp_claim_age: float = 65
    lp_lump_sum: bool = False           # True 一次領；False 月領
    # 勞保老年年金
    li_enabled: bool = True
    li_avg_wage: float = 45_800         # 平均月投保薪資
    li_years_now: float = 0.0           # 目前已投保年資
    li_claim_age: float = 65
    li_manual_monthly: float = 0.0      # >0 則直接採用此金額（以 65 歲請領為基準）
    accounts: list = field(default_factory=list)
    loans: list = field(default_factory=list)


def to_dict(s: Settings) -> dict:
    return asdict(s)


def from_dict(d: dict) -> Settings:
    s = Settings()
    for k, v in d.items():
        if k in ("accounts", "loans") or not hasattr(s, k):
            continue
        setattr(s, k, v)
    s.accounts = [Account(**{k: v for k, v in a.items() if k in Account.__dataclass_fields__})
                  for a in d.get("accounts", [])]
    s.loans = [Loan(**{k: v for k, v in l.items() if k in Loan.__dataclass_fields__})
               for l in d.get("loans", [])]
    return s


def monthly_rate(annual_pct: float) -> float:
    return (1 + annual_pct / 100.0) ** (1 / 12) - 1


def parse_ym(text: str) -> Optional[int]:
    """'YYYY-MM' -> 絕對月數 (year*12+month-1)。空字串回傳 None。"""
    text = (text or "").strip().replace("/", "-")
    if not text:
        return None
    y, m = text.split("-")
    y, m = int(y), int(m)
    if not 1 <= m <= 12:
        raise ValueError(f"月份錯誤：{text}")
    return y * 12 + m - 1


def annuity_payment(principal: float, annual_pct: float, months: int) -> float:
    if months <= 0:
        return 0.0
    r = annual_pct / 100.0 / 12
    if r == 0:
        return principal / months
    return principal * r / (1 - (1 + r) ** -months)


def labor_insurance_monthly(s: Settings) -> float:
    """勞保老年年金月給付（名目，固定）。"""
    if not s.li_enabled:
        return 0.0
    if s.li_manual_monthly > 0:
        base = s.li_manual_monthly
    else:
        years = s.li_years_now + max(0.0, s.retire_age - s.current_age)
        a = s.li_avg_wage * years * 0.00775 + 3000
        b = s.li_avg_wage * years * 0.0155
        base = max(a, b)
    diff = s.li_claim_age - 65
    diff = max(-5, min(5, diff))
    return base * (1 + 0.04 * diff)  # 提前每年 -4%，延後每年 +4%


def validate(s: Settings) -> list[str]:
    errs = []
    if s.current_age < 0 or s.current_age >= s.life_expectancy:
        errs.append("目前年齡必須小於預期壽命")
    if s.retire_age < s.current_age:
        errs.append("退休年齡不可小於目前年齡")
    if s.retire_age > s.life_expectancy:
        errs.append("退休年齡不可大於預期壽命")
    if not 0 <= s.lp_self_pct <= 6:
        errs.append("勞退自提比例需介於 0~6%")
    for l in s.loans:
        try:
            a, b = parse_ym(l.start), parse_ym(l.end)
        except Exception:
            errs.append(f"貸款「{l.name}」的日期格式需為 YYYY-MM")
            continue
        if a is None:
            errs.append(f"貸款「{l.name}」缺少起始年月")
        elif b is None and not (l.mode == "amort" and l.years > 0):
            errs.append(f"貸款「{l.name}」缺少結束年月")
        elif b is not None and b < a:
            errs.append(f"貸款「{l.name}」結束早於起始")
    return errs


@dataclass
class Row:
    age: float
    income: float            # 該年稅後薪資收入
    pension_income: float    # 該年勞保年金 + 勞退月領
    expense: float           # 該年生活支出
    loan_paid: float
    invested: float          # 該年新增投資
    account_balances: list
    free_cash: float
    lp_balance: float
    loan_balance: float
    net_worth: float
    real_net_worth: float


@dataclass
class Result:
    rows: list
    account_names: list
    retire_net_worth: float
    retire_real_net_worth: float
    depleted_age: Optional[float]   # 資產耗盡年齡（None = 撐到預期壽命）
    li_monthly: float
    lp_monthly: float
    lp_at_claim: float
    monthly_surplus_now: float
    warnings: list


def simulate(s: Settings, today: Optional[dt.date] = None) -> Result:
    today = today or dt.date.today()
    errs = validate(s)
    if errs:
        raise ValueError("；".join(errs))
    now_abs = today.year * 12 + today.month - 1
    total_m = int(round((s.life_expectancy - s.current_age) * 12))
    retire_m = int(round((s.retire_age - s.current_age) * 12))
    infl_m = (1 + s.inflation / 100) ** (1 / 12)
    gt = 1 - s.gains_tax_rate / 100

    # 帳戶
    bal = [a.cash for a in s.accounts]
    acc_rate = [monthly_rate(a.annual_return) for a in s.accounts]
    acc_add_m = [min(int(round(a.years * 12)), retire_m) for a in s.accounts]
    free = s.savings_cash
    free_rate = monthly_rate(s.savings_rate)

    # 勞退
    lp = s.lp_balance
    lp_r = monthly_rate(s.lp_return)
    claim_m = max(int(round((s.lp_claim_age - s.current_age) * 12)), retire_m)
    lp_pay = 0.0
    lp_at_claim = 0.0
    lp_enabled = s.lp_enabled

    li_pay = labor_insurance_monthly(s)
    li_start_m = max(int(round((s.li_claim_age - s.current_age) * 12)), 0)

    # 貸款
    loan_sched = []
    for l in s.loans:
        a = parse_ym(l.start)
        b = parse_ym(l.end)
        if l.mode == "amort":
            n = (b - a + 1) if b is not None else int(round(l.years * 12))
            pay = annuity_payment(l.principal, l.annual_rate, n)
            loan_sched.append({"a": a, "n": n, "pay": pay, "bal": l.principal,
                               "r": l.annual_rate / 100 / 12, "amort": True})
        else:
            n = b - a + 1
            loan_sched.append({"a": a, "n": n, "pay": l.monthly_payment, "bal": 0.0,
                               "r": 0.0, "amort": False})
    # 追趕：amort 貸款在「今天」之前已還款的期數，讓餘額正確
    for ls in loan_sched:
        if ls["amort"]:
            past = min(max(now_abs - ls["a"], 0), ls["n"])
            for _ in range(past):
                ls["bal"] = ls["bal"] * (1 + ls["r"]) - ls["pay"]
            ls["bal"] = max(ls["bal"], 0.0)

    def loan_state(m):
        """回傳 (本月扣款, 貸款餘額)，並推進 amort 餘額。"""
        paid, balance = 0.0, 0.0
        for ls in loan_sched:
            k = now_abs + m - ls["a"]  # 第 k 期（0 起算）
            if 0 <= k < ls["n"]:
                paid += ls["pay"]
                if ls["amort"]:
                    ls["bal"] = max(ls["bal"] * (1 + ls["r"]) - ls["pay"], 0.0)
        for ls in loan_sched:
            k = now_abs + m - ls["a"]
            if ls["amort"]:
                balance += ls["bal"]
            else:
                remain = ls["n"] - (k + 1)
                if k < 0:
                    remain = ls["n"]
                balance += max(remain, 0) * ls["pay"]
        return paid, balance

    # 追加「今日之前」fixed 貸款不需處理；amort 已追趕。但 amort 若 k<0（未開始）餘額應為 0 直到開始
    for ls in loan_sched:
        if ls["amort"] and now_abs < ls["a"]:
            ls["_future_principal"] = ls["bal"]
            ls["bal"] = 0.0

    warnings = []
    rows = []
    depleted = None
    y_income = y_pension = y_exp = y_loan = y_inv = 0.0
    retire_nw = retire_real = 0.0
    surplus_now = None
    gross0 = s.monthly_income

    for m in range(total_m):
        yr = m // 12
        retired = m >= retire_m
        # 未來才開始的 amort 貸款：到期初放入本金
        for ls in loan_sched:
            if ls["amort"] and "_future_principal" in ls and now_abs + m == ls["a"]:
                ls["bal"] = ls.pop("_future_principal")

        # 報酬（先複利）
        for i in range(len(bal)):
            if bal[i] > 0:
                bal[i] += bal[i] * acc_rate[i] * gt
        if free > 0:
            free += free * free_rate * gt
        if lp > 0:
            lp += lp * lp_r

        # 收入
        net_salary = 0.0
        self_contrib = 0.0
        if not retired:
            gross = gross0 * (1 + s.income_growth / 100) ** yr
            net_salary = gross * (1 - s.income_tax_rate / 100)
            if s.lp_enabled:
                wage = min(s.lp_wage if s.lp_wage > 0 else gross, LABOR_PENSION_WAGE_CAP)
                if s.lp_wage > 0:
                    wage = min(s.lp_wage * (1 + s.income_growth / 100) ** yr, LABOR_PENSION_WAGE_CAP)
                lp += wage * s.lp_employer_pct / 100
                self_contrib = wage * s.lp_self_pct / 100
                lp += self_contrib
                net_salary -= self_contrib

        # 勞退領取
        pension = 0.0
        if lp_enabled and m == claim_m:
            lp_at_claim = lp
            if s.lp_lump_sum:
                free += lp
                lp = 0.0
                lp_enabled = False
            else:
                n_left = max(total_m - m, 1)
                lp_pay = annuity_payment(lp, s.lp_return, n_left)
        if lp_enabled and m >= claim_m and not s.lp_lump_sum:
            take = min(lp_pay, lp)
            lp -= take
            pension += take
        if li_pay > 0 and m >= li_start_m:
            pension += li_pay

        # 支出
        infl = infl_m ** m
        expense = (s.retire_expense if retired else s.monthly_expense) * infl
        loan_paid, loan_bal = loan_state(m)

        # 投資加碼
        invested = 0.0
        if not retired:
            for i, a in enumerate(s.accounts):
                if m < acc_add_m[i]:
                    bal[i] += a.monthly_add
                    invested += a.monthly_add

        cash_flow = net_salary + pension - expense - loan_paid - invested
        if m == 0:
            surplus_now = cash_flow
        if cash_flow >= 0:
            free += cash_flow
        else:
            need = -cash_flow
            take = min(max(free, 0.0), need)
            free -= take
            need -= take
            for i in range(len(bal)):
                if need <= 0:
                    break
                t = min(bal[i], need)
                bal[i] -= t
                need -= t
            if need > 1e-6:
                free -= need  # 負債（資金耗盡後的缺口）
                if depleted is None:
                    depleted = s.current_age + m / 12

        y_income += net_salary
        y_pension += pension
        y_exp += expense
        y_loan += loan_paid
        y_inv += invested

        if (m + 1) % 12 == 0 or m == total_m - 1:
            nw = sum(bal) + free + lp - loan_bal
            real = nw / (infl_m ** (m + 1))
            rows.append(Row(
                age=round(s.current_age + (m + 1) / 12, 2),
                income=y_income, pension_income=y_pension, expense=y_exp,
                loan_paid=y_loan, invested=y_inv,
                account_balances=list(bal), free_cash=free, lp_balance=lp,
                loan_balance=loan_bal, net_worth=nw, real_net_worth=real))
            y_income = y_pension = y_exp = y_loan = y_inv = 0.0
        if m + 1 == retire_m:
            retire_nw = sum(bal) + free + lp - loan_bal
            retire_real = retire_nw / (infl_m ** (m + 1))

    if retire_m == 0:
        retire_nw = sum(a.cash for a in s.accounts) + s.savings_cash + s.lp_balance
        retire_real = retire_nw
    if s.lp_enabled and s.lp_claim_age < s.retire_age:
        warnings.append("勞退請領年齡早於退休年齡，已視為退休時才請領")
    if surplus_now is not None and surplus_now < 0 and s.retire_age > s.current_age:
        warnings.append("目前每月現金流為負，不足部分會動用活存/投資帳戶")
    return Result(rows=rows, account_names=[a.name for a in s.accounts],
                  retire_net_worth=retire_nw, retire_real_net_worth=retire_real,
                  depleted_age=depleted, li_monthly=li_pay, lp_monthly=lp_pay,
                  lp_at_claim=lp_at_claim, monthly_surplus_now=surplus_now or 0.0,
                  warnings=warnings)
