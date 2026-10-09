"""退休收益預測引擎（純 Python，不依賴 GUI）。以「月」為單位模擬，名目金額（NT$）。"""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field, asdict
from typing import Optional

LABOR_PENSION_WAGE_CAP = 150_000  # 勞退提繳工資上限（預設，可在設定中調整）
CASH = "活存"            # 內建帳戶名稱：活存/現金
BUCKET = "生活費帳戶"      # 內建帳戶名稱：退休後生活費帳戶


@dataclass
class Stage:
    """投資時間段（以年齡計，含起不含迄）。"""
    start_age: float = 0.0
    end_age: float = 120.0
    annual_return: float = 5.0   # 該段預期年均報酬率 %
    monthly_add: float = 0.0     # 該段每月增額（僅退休前有效）


def stage_at(stages: list, age: float) -> tuple:
    """回傳 (年報酬率 %, 每月增額)。時間段之外：沿用最近一段的報酬率並停止加碼。"""
    if not stages:
        return 0.0, 0.0
    for st in stages:
        if st.start_age <= age < st.end_age:
            return st.annual_return, st.monthly_add
    prev = [st for st in stages if st.end_age <= age]
    if prev:
        return max(prev, key=lambda x: x.end_age).annual_return, 0.0
    return min(stages, key=lambda x: x.start_age).annual_return, 0.0


@dataclass
class Account:
    name: str = "投資帳戶"
    cash: float = 0.0            # 目前現金/本金
    stages: list = field(default_factory=list)  # list[Stage]

    @staticmethod
    def simple(name, cash, monthly_add, annual_return, years, start_age=0.0):
        return Account(name, cash, [Stage(start_age, start_age + years, annual_return, monthly_add)])


@dataclass
class Loan:
    name: str = "房貸"
    mode: str = "fixed"          # fixed: 固定月扣款 / amort: 本息平均攤還
    monthly_payment: float = 0.0  # fixed 模式
    principal: float = 0.0        # amort 模式：原貸款金額
    annual_rate: float = 2.0      # amort 模式：年利率 %
    pay_account: str = ""         # 還款由哪個帳戶支付；空白 = 預設（退休前活存、退休後生活費帳戶）
    start: str = ""               # "YYYY-MM"
    end: str = ""                 # "YYYY-MM"（含）；amort 模式以年限推算時可留空
    years: float = 0.0            # amort 模式：貸款年限（end 空白時使用）


@dataclass
class ExtraIncome:
    """額外收入（兼職、租金、股利…）。金額以名目計，年金額平均分攤到每月。"""
    name: str = "額外收入"
    amount: float = 0.0
    freq: str = "month"          # month / year
    start_age: float = 0.0
    end_age: float = 65.0        # 含起不含迄
    growth: float = 0.0          # 每年成長 %
    taxable: bool = True         # 是否計入年度所得稅
    account: str = ""            # 收入存入哪個帳戶；空白 = 預設


@dataclass
class Insurance:
    """保險：保費有期限，可有滿期金。"""
    name: str = "保險"
    premium: float = 0.0
    freq: str = "month"          # month / year（年繳於保單年度起始月扣款）
    start_age: float = 0.0
    end_age: float = 65.0        # 繳費期間含起不含迄
    inflation_adjust: bool = False
    pay_account: str = ""        # 保費由哪個帳戶支付；空白 = 預設
    payout: float = 0.0          # 滿期金/理賠金（名目）
    payout_age: float = 0.0      # 領取年齡；0 = 繳費結束年齡
    payout_to: str = ""          # 入帳帳戶名稱；空白或找不到 = 活存


@dataclass
class Property:
    """不動產：計入淨資產，可設定出售並償還綁定貸款。"""
    name: str = "自住房"
    value: float = 0.0           # 目前市值
    appreciation: float = 2.0    # 年增值率 %
    sell_age: float = 0.0        # 0 = 不出售
    sell_cost: float = 4.0       # 交易成本 %（仲介、稅費）
    purchase_price: float = 0.0  # 購入價（0 = 不計算獲利）
    sell_tax_rate: float = 0.0   # 出售獲利稅率 %（如房地合一稅；以售價 − 成本 − 購入價為獲利）
    loan_name: str = ""          # 出售時一併還清的貸款（名稱）
    proceeds_to: str = ""        # 售屋款入帳帳戶；空白或找不到 = 活存


@dataclass
class ExtraExpense:
    """其他固定支出（子女教育、孝親費、旅遊…），有起訖年齡。"""
    name: str = "額外支出"
    amount: float = 0.0          # 今日幣值
    freq: str = "month"          # month / year（年金額平均分攤到每月）
    start_age: float = 0.0
    end_age: float = 65.0        # 含起不含迄
    inflation_adjust: bool = True
    pay_account: str = ""        # 由哪個帳戶支付；空白 = 預設


@dataclass
class OneOff:
    """一次性收支：購車、出國、子女教育金、遺產…"""
    name: str = "一次性收支"
    kind: str = "out"            # out 支出 / in 收入
    amount: float = 0.0          # 名目金額
    age: float = 0.0
    account: str = ""            # 收入入帳帳戶；空白或找不到 = 活存（支出走一般現金流）


@dataclass
class Policy:
    """帳戶規則：cap = 超過上限的部分轉出；fixed = 每年 1 月調整到固定額度（不足由來源補、超出轉出）。
    account 為 活存 / 生活費帳戶 / 投資帳戶名稱 / 退休金帳戶。生活費帳戶的額度為 bucket_amount。"""
    account: str = CASH
    mode: str = "none"           # none / cap / fixed
    limit: float = 0.0           # 上限或固定額度（名目金額）
    overflow_to: str = ""        # 超出部分流向的帳戶
    refill_from: str = ""        # 固定額度不足時的補足來源；空白 = 依投資帳戶清單順序


@dataclass
class Settings:
    current_age: float = 35
    retire_age: float = 65
    life_expectancy: float = 90
    salary_net: float = 57_000          # 實領月薪（已扣勞健保、預扣稅、自提）
    salary_withheld: float = 3_000      # 每月預扣所得稅（稅款準備金；每年 5 月結算）
    income_growth: float = 2.0          # 每年調薪 %（實領與預扣同步成長）
    income_tax_rate: float = 5.0        # 年度結算有效稅率 %（課稅所得 = 薪資 + 應稅額外收入）
    salary_account: str = ""            # 實領薪水/獎金存入的帳戶；空白 = 預設（退休前活存）
    pension_account: str = ""           # 年金/退休金月領存入的帳戶；空白 = 預設
    expense_account: str = ""           # 生活支出、醫療、一次性支出由哪個帳戶支付；空白 = 預設
    bonus_months: float = 0.0           # 年終/績效獎金（以實領月薪的幾個月計）
    bonus_month: float = 2              # 獎金發放月份（1~12）
    monthly_expense: float = 30_000     # 目前每月生活支出（今日幣值）
    retire_expense: float = 30_000      # 退休後每月生活支出（今日幣值）
    inflation: float = 2.0              # 通膨率 %
    gains_tax_rate: float = 0.0         # 投資獲利稅率 %
    savings_cash: float = 0.0           # 活存/未投入現金
    savings_rate: float = 1.0           # 活存年利率 %
    bucket_amount: float = 1_800_000    # 退休後「生活費帳戶」每年年初補足到此金額（今日幣值，隨通膨調整）
    # 勞退新制
    lp_enabled: bool = True
    lp_wage: float = 0.0                # 提繳工資；0 = 取月收入
    lp_wage_cap: float = LABOR_PENSION_WAGE_CAP  # 提繳工資上限
    lp_employer_pct: float = 6.0
    lp_self_pct: float = 0.0            # 自提 0~6%
    lp_balance: float = 0.0             # 帳戶現有餘額
    lp_return: float = 3.0              # 帳戶年收益率 %
    lp_claim_age: float = 65
    employer_lump: float = 0.0          # 雇主另給的退休金（退休時一次領，名目金額，轉入退休金帳戶）
    lp_lump_sum: bool = True            # True 一次領（轉入退休金帳戶）；False 月領
    lump_stages: list = field(default_factory=lambda: [Stage(0.0, 120.0, 4.0, 0.0)])  # 退休金帳戶投資階段
    # 勞保老年年金
    li_enabled: bool = True
    li_avg_wage: float = 45_800         # 平均月投保薪資
    li_years_now: float = 0.0           # 目前已投保年資
    li_claim_age: float = 65
    li_manual_monthly: float = 0.0      # >0 則直接採用此金額（以 65 歲請領為基準）
    # 退休後醫療費用
    medical_start_age: float = 70
    medical_monthly: float = 5_000      # 起始年齡時每月醫療費用（今日幣值）
    medical_growth: float = 2.0         # 醫療費用高於一般通膨的年增幅 %
    scenario_delta: float = 2.0         # 悲觀/樂觀情境：投資帳戶報酬率 ∓ 百分點
    accounts: list = field(default_factory=list)
    loans: list = field(default_factory=list)
    extra_incomes: list = field(default_factory=list)
    insurances: list = field(default_factory=list)
    properties: list = field(default_factory=list)
    extra_expenses: list = field(default_factory=list)
    one_offs: list = field(default_factory=list)
    policies: list = field(default_factory=list)


def to_dict(s: Settings) -> dict:
    return asdict(s)


def _stages(lst) -> list:
    return [Stage(**{k: v for k, v in d.items() if k in Stage.__dataclass_fields__}) for d in lst]


def _objs(cls, lst) -> list:
    return [cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__}) for d in lst or []]


def from_dict(d: dict) -> Settings:
    s = Settings()
    for k, v in d.items():
        if k in ("accounts", "loans", "lump_stages", "extra_incomes", "insurances", "properties",
                 "extra_expenses", "one_offs", "policies") \
                or not hasattr(s, k):
            continue
        setattr(s, k, v)
    if "monthly_income" in d and "salary_net" not in d:  # 舊格式：稅前月薪 + 稅率
        gross, rate = d["monthly_income"], d.get("income_tax_rate", 5.0)
        s.salary_net, s.salary_withheld = gross * (1 - rate / 100), gross * rate / 100
    s.extra_incomes = _objs(ExtraIncome, d.get("extra_incomes"))
    s.insurances = _objs(Insurance, d.get("insurances"))
    s.properties = _objs(Property, d.get("properties"))
    s.extra_expenses = _objs(ExtraExpense, d.get("extra_expenses"))
    s.one_offs = _objs(OneOff, d.get("one_offs"))
    s.policies = _objs(Policy, d.get("policies"))
    if "lump_stages" in d:
        s.lump_stages = _stages(d["lump_stages"])
    s.accounts = []
    for a in d.get("accounts", []):
        if "stages" in a:  # 新格式
            s.accounts.append(Account(a.get("name", "投資帳戶"), a.get("cash", 0.0), _stages(a["stages"])))
        else:  # 舊格式：單一報酬率 + 投資年限
            s.accounts.append(Account.simple(a.get("name", "投資帳戶"), a.get("cash", 0.0),
                                             a.get("monthly_add", 0.0), a.get("annual_return", 5.0),
                                             a.get("years", 20.0), s.current_age))
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
    if not 0 <= s.lp_self_pct <= 100:
        errs.append("個人提繳比例需介於 0~100%")
    for a in list(s.accounts) + [Account("退休金帳戶", 0, s.lump_stages)]:
        for st in a.stages:
            if st.end_age <= st.start_age:
                errs.append(f"帳戶「{a.name}」的時間段結束年齡需大於起始年齡")
    for x in s.extra_incomes:
        if x.end_age <= x.start_age:
            errs.append(f"額外收入「{x.name}」結束年齡需大於起始年齡")
    for x in s.insurances:
        if x.end_age <= x.start_age:
            errs.append(f"保險「{x.name}」結束年齡需大於起始年齡")
    for x in s.extra_expenses:
        if x.end_age <= x.start_age:
            errs.append(f"額外支出「{x.name}」結束年齡需大於起始年齡")
    for p_ in s.policies:
        if p_.limit < 0:
            errs.append(f"帳戶規則「{p_.account}」的金額不可為負")
    if not 1 <= s.bonus_month <= 12:
        errs.append("獎金發放月份需介於 1~12")
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
    income: float            # 該年實領薪資
    pension_income: float    # 該年勞保年金 + 勞退月領
    expense: float           # 該年生活支出
    extra_income: float      # 該年額外收入
    insurance: float         # 該年保險保費
    medical: float           # 該年醫療費用
    extra_expense: float     # 該年其他固定支出
    one_off: float           # 該年一次性收支淨額（收入為正）
    tax_settle: float        # 該年稅款結算（正 = 退稅，負 = 補稅）
    loan_paid: float
    invested: float          # 該年新增投資
    account_balances: list
    free_cash: float
    bucket: float            # 退休生活費帳戶
    lp_balance: float
    loan_balance: float
    property_value: float    # 不動產市值
    net_worth: float         # 含不動產
    real_net_worth: float
    liquid_net_worth: float  # 不含不動產


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
    property_sales: list = field(default_factory=list)   # 不動產出售明細（dict 清單）
    cashflow: dict = field(default_factory=dict)         # 第一年「平均每月」現金流明細


def simulate(s: Settings, today: Optional[dt.date] = None, return_delta: float = 0.0) -> Result:
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
    accs = list(s.accounts)
    lump_idx = None
    if (s.lp_enabled and s.lp_lump_sum) or s.employer_lump > 0:  # 一次領 → 退休金帳戶（排在投資帳戶之後）
        accs.append(Account("退休金帳戶", 0.0, s.lump_stages))
        lump_idx = len(accs) - 1
    n_real = len(s.accounts)
    bal = [a.cash for a in accs]
    free = s.savings_cash
    bucket = 0.0   # 退休生活費帳戶
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
    for li_, l in enumerate(s.loans):
        a = parse_ym(l.start)
        b = parse_ym(l.end)
        if l.mode == "amort":
            n = (b - a + 1) if b is not None else int(round(l.years * 12))
            pay = annuity_payment(l.principal, l.annual_rate, n)
            loan_sched.append({"a": a, "n": n, "pay": pay, "bal": l.principal, "name": l.name, "idx": li_,
                               "r": l.annual_rate / 100 / 12, "amort": True, "cancelled": False})
        else:
            n = b - a + 1
            loan_sched.append({"a": a, "n": n, "pay": l.monthly_payment, "bal": 0.0, "name": l.name, "idx": li_,
                               "r": 0.0, "amort": False, "cancelled": False})
    # 追趕：amort 貸款在「今天」之前已還款的期數，讓餘額正確
    for ls in loan_sched:
        if ls["amort"]:
            past = min(max(now_abs - ls["a"], 0), ls["n"])
            for _ in range(past):
                ls["bal"] = ls["bal"] * (1 + ls["r"]) - ls["pay"]
            ls["bal"] = max(ls["bal"], 0.0)

    def loan_state(m):
        """回傳 (本月扣款, 貸款餘額)，並推進 amort 餘額。"""
        paid, balance, pays = 0.0, 0.0, []
        for ls in loan_sched:
            if ls["cancelled"]:
                continue
            k = now_abs + m - ls["a"]  # 第 k 期（0 起算）
            if 0 <= k < ls["n"]:
                paid += ls["pay"]
                pays.append((ls["idx"], ls["pay"]))
                if ls["amort"]:
                    ls["bal"] = max(ls["bal"] * (1 + ls["r"]) - ls["pay"], 0.0)
        for ls in loan_sched:
            if ls["cancelled"]:
                continue
            k = now_abs + m - ls["a"]
            if ls["amort"]:
                balance += ls["bal"]
            else:
                remain = ls["n"] - (k + 1)
                if k < 0:
                    remain = ls["n"]
                balance += max(remain, 0) * ls["pay"]
        return paid, balance, pays

    # 追加「今日之前」fixed 貸款不需處理；amort 已追趕。但 amort 若 k<0（未開始）餘額應為 0 直到開始
    for ls in loan_sched:
        if ls["amort"] and now_abs < ls["a"]:
            ls["_future_principal"] = ls["bal"]
            ls["bal"] = 0.0

    def loan_remaining(ls, m):
        """出售不動產時需還清的貸款餘額（fixed 貸款以剩餘應付總額估算）。"""
        if ls["cancelled"]:
            return 0.0
        if ls["amort"]:
            return ls["bal"] if now_abs + m >= ls["a"] else ls["bal"] + ls.get("_future_principal", 0.0)
        k = now_abs + m - ls["a"]
        return max(ls["n"] - max(k, 0), 0) * ls["pay"]

    warnings = []
    rows = []
    property_sales = []
    depleted = None
    y_income = y_pension = y_exp = y_loan = y_inv = 0.0
    y_extra = y_ins = y_med = y_tax = y_xexp = y_oneoff = 0.0
    retire_nw = retire_real = 0.0
    surplus_now = None
    fy = {k: 0.0 for k in ("salary", "extra", "pension", "tax", "living", "xexp", "insurance", "loan", "medical",
                           "oneoff", "invest")}
    names = [a.name for a in accs]
    tax_year: dict = {}          # 日曆年 -> [已預扣, 課稅所得]
    prop_sold = [False] * len(s.properties)
    sale_m = [int(round((p_.sell_age - s.current_age) * 12)) if p_.sell_age > 0 else None
              for p_ in s.properties]

    def valid(name):
        return name in names or name in (CASH, BUCKET)

    def get_bal(name):
        if name == CASH:
            return free
        if name == BUCKET:
            return bucket
        return bal[names.index(name)]

    def add_bal(name, amt):
        nonlocal free, bucket
        if name == CASH:
            free += amt
        elif name == BUCKET:
            bucket += amt
        else:
            bal[names.index(name)] += amt

    def credit(amount, dest):
        """明確指定的入帳（滿期金、售屋款、一次性收入）；空白或找不到帳戶 → 活存。"""
        add_bal(dest if valid(dest) else CASH, amount)

    flow = [0.0, 0.0]   # 本月「預設現金流」：[收入, 支出]

    def route_in(amount, dest):
        """收入：指定帳戶有效則直接存入，否則併入預設現金流。"""
        if amount <= 0:
            return
        if valid(dest):
            add_bal(dest, amount)
        else:
            flow[0] += amount

    def route_out(amount, src):
        """支出：由指定帳戶支付；該帳戶餘額不足的部分併入預設現金流（再動用其他帳戶）。"""
        if amount <= 0:
            return
        if valid(src):
            take = min(max(get_bal(src), 0.0), amount)
            add_bal(src, -take)
            amount -= take
        flow[1] += amount

    def draw(need, free_first, exclude=None):
        """依序從活存/投資帳戶提領（不動生活費帳戶），回傳實際領到的金額。"""
        nonlocal free
        got = 0.0

        def from_free():
            nonlocal free, got
            if exclude != CASH:
                t_ = min(max(free, 0.0), need - got)
                free -= t_
                got += t_
        if free_first:
            from_free()
        for i in range(len(bal)):
            if got >= need:
                break
            if names[i] == exclude:
                continue
            t_ = min(max(bal[i], 0.0), need - got)
            bal[i] -= t_
            got += t_
        if not free_first and got < need:
            from_free()
        return got

    pol = {p_.account: p_ for p_ in s.policies if p_.mode in ("cap", "fixed") or p_.account == BUCKET}

    def policy_year_start():
        """每年 1 月：「固定額度」帳戶調整到額度（不足由來源補、超出轉出）。"""
        for nm, p_ in pol.items():
            if p_.mode != "fixed" or nm == BUCKET or not valid(nm):
                continue
            cur = get_bal(nm)
            if cur < p_.limit:
                if valid(p_.refill_from) and p_.refill_from != nm:
                    take = min(max(get_bal(p_.refill_from), 0.0), p_.limit - cur)
                    add_bal(p_.refill_from, -take)
                    add_bal(nm, take)
                else:
                    add_bal(nm, draw(p_.limit - cur, nm != CASH, exclude=nm))
            elif cur > p_.limit and valid(p_.overflow_to) and p_.overflow_to != nm:
                ex = cur - p_.limit
                add_bal(nm, -ex)
                add_bal(p_.overflow_to, ex)

    def policy_sweep():
        """每月月底：「上限」帳戶超過上限的部分轉到指定帳戶。"""
        for nm, p_ in pol.items():
            if p_.mode == "cap" and valid(nm) and valid(p_.overflow_to) and p_.overflow_to != nm:
                ex = get_bal(nm) - p_.limit
                if ex > 0:
                    add_bal(nm, -ex)
                    add_bal(p_.overflow_to, ex)

    def refill(m_next):
        """每年年初：把生活費帳戶補足到設定金額（隨通膨調整）；超出的部分依規則轉出。"""
        nonlocal bucket
        target = s.bucket_amount * infl_m ** m_next
        p_ = pol.get(BUCKET)
        if bucket < target:
            if p_ and valid(p_.refill_from) and p_.refill_from != BUCKET:
                take = min(max(get_bal(p_.refill_from), 0.0), target - bucket)
                add_bal(p_.refill_from, -take)
                bucket += take
            else:
                bucket += draw(target - bucket, False)
        elif p_ and bucket > target and valid(p_.overflow_to) and p_.overflow_to != BUCKET:
            ex = bucket - target
            bucket -= ex
            add_bal(p_.overflow_to, ex)

    if retire_m == 0:
        refill(0)

    for m in range(total_m):
        yr = m // 12
        age = s.current_age + m / 12
        retired = m >= retire_m
        cal_year = today.year + (today.month - 1 + m) // 12
        cal_month = (today.month - 1 + m) % 12 + 1
        flow[0] = flow[1] = 0.0
        if cal_month == 1:
            policy_year_start()
        # 未來才開始的 amort 貸款：到期初放入本金
        for ls in loan_sched:
            if ls["amort"] and "_future_principal" in ls and now_abs + m == ls["a"]:
                ls["bal"] = ls.pop("_future_principal")

        # 報酬（先複利）；各帳戶依所在時間段取報酬率與加碼額
        adds = [0.0] * len(bal)
        for i in range(len(bal)):
            rate, add = stage_at(accs[i].stages, age)
            rate += return_delta
            if bal[i] > 0:
                bal[i] += bal[i] * monthly_rate(rate) * gt
            if i < n_real:
                adds[i] = add
        if free > 0:
            free += free * free_rate * gt
        if bucket > 0:
            bucket += bucket * free_rate * gt
        if lp > 0:
            lp += lp * lp_r

        # 收入：實領薪水（預扣所得稅另列入稅款準備金）、額外收入
        net_salary = withheld = 0.0
        taxable_inc = 0.0
        if not retired:
            gf = (1 + s.income_growth / 100) ** yr
            net_salary = s.salary_net * gf
            withheld = s.salary_withheld * gf
            taxable_inc = net_salary + withheld
            if s.lp_enabled:
                base = s.lp_wage * gf if s.lp_wage > 0 else net_salary + withheld
                wage = min(base, s.lp_wage_cap)
                lp += wage * s.lp_employer_pct / 100 + wage * s.lp_self_pct / 100  # 自提已含在實領薪水的扣款中
        if not retired and s.bonus_months > 0 and cal_month == int(s.bonus_month):
            bonus = net_salary * s.bonus_months
            net_salary += bonus
            taxable_inc += bonus
        extra = 0.0
        for x in s.extra_incomes:
            if x.start_age <= age < x.end_age:
                amt = x.amount * (1 + x.growth / 100) ** max(age - x.start_age, 0) / (12 if x.freq == "year" else 1)
                extra += amt
                route_in(amt, x.account)
                if x.taxable:
                    taxable_inc += amt
        route_in(net_salary, s.salary_account)
        ty = tax_year.setdefault(cal_year, [0.0, 0.0])
        ty[0] += withheld
        ty[1] += taxable_inc
        tax_settle = 0.0
        if cal_month == 5 and (cal_year - 1) in tax_year:  # 每年 5 月結算上一年度所得稅（多退少補）
            w_, inc_ = tax_year.pop(cal_year - 1)
            tax_settle = w_ - inc_ * s.income_tax_rate / 100
            if tax_settle >= 0:
                flow[0] += tax_settle
            else:
                flow[1] -= tax_settle

        # 雇主另給的退休金：退休當月進入退休金帳戶
        if s.employer_lump > 0 and m == retire_m:
            bal[lump_idx] += s.employer_lump

        # 勞退領取
        pension = 0.0
        if lp_enabled and m == claim_m:
            lp_at_claim = lp
            if s.lp_lump_sum:
                bal[lump_idx] += lp
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
        route_in(pension, s.pension_account)

        # 支出
        infl = infl_m ** m
        expense = (s.retire_expense if retired else s.monthly_expense) * infl
        medical = 0.0
        if age >= s.medical_start_age and s.medical_monthly > 0:
            medical = s.medical_monthly * infl * (1 + s.medical_growth / 100) ** (age - s.medical_start_age)

        # 其他固定支出、一次性收支
        route_out(expense + medical, s.expense_account)
        extra_exp = 0.0
        for x in s.extra_expenses:
            if x.start_age <= age < x.end_age:
                amt = x.amount / (12 if x.freq == "year" else 1) * (infl if x.inflation_adjust else 1.0)
                extra_exp += amt
                route_out(amt, x.pay_account)
        one_in = one_out = 0.0
        for x in s.one_offs:
            if x.amount > 0 and m == int(round((x.age - s.current_age) * 12)):
                if x.kind == "in":
                    one_in += x.amount
                    credit(x.amount, x.account)
                else:
                    one_out += x.amount
                    route_out(x.amount, s.expense_account)

        # 保險：保費、滿期金
        insurance = 0.0
        for x in s.insurances:
            sm = int(round((x.start_age - s.current_age) * 12))
            em = int(round((x.end_age - s.current_age) * 12))
            if sm <= m < em and (x.freq != "year" or (m - sm) % 12 == 0):
                prem = x.premium * (infl if x.inflation_adjust else 1.0)
                insurance += prem
                route_out(prem, x.pay_account)
            if x.payout > 0 and m == int(round(((x.payout_age or x.end_age) - s.current_age) * 12)):
                credit(x.payout, x.payout_to)

        # 不動產出售：售屋款扣交易成本與綁定貸款後入帳
        for i, p_ in enumerate(s.properties):
            if sale_m[i] is not None and m == sale_m[i] and not prop_sold[i]:
                prop_sold[i] = True
                price = p_.value * (1 + p_.appreciation / 100) ** (m / 12)
                cost = price * p_.sell_cost / 100
                payoff = 0.0
                for ls in loan_sched:
                    if p_.loan_name and ls["name"] == p_.loan_name:
                        payoff += loan_remaining(ls, m)
                        ls["cancelled"] = True
                gain = price - cost - p_.purchase_price if p_.purchase_price > 0 else None
                tax = max(gain, 0.0) * p_.sell_tax_rate / 100 if gain is not None else 0.0
                net = price - cost - payoff - tax
                property_sales.append({
                    "name": p_.name, "age": round(age, 1), "price": price, "cost": cost, "payoff": payoff,
                    "tax": tax, "net_cash": net, "gain": gain, "gain_after_tax": None if gain is None else gain - tax,
                    "gain_vs_now": price - p_.value})
                credit(net, p_.proceeds_to)
        loan_paid, loan_bal, loan_pays = loan_state(m)
        for li_, pay_ in loan_pays:
            route_out(pay_, s.loans[li_].pay_account)

        invested = 0.0
        if not retired:
            for i in range(n_real):
                bal[i] += adds[i]
                invested += adds[i]

        flow[1] += invested   # 每月投資加碼一律由預設現金流支應
        outflow = expense + medical + insurance + loan_paid + extra_exp + one_out
        if m < 12:
            for k_, v_ in (("salary", net_salary), ("extra", extra), ("pension", pension), ("tax", tax_settle),
                           ("living", expense), ("xexp", extra_exp), ("insurance", insurance),
                           ("loan", loan_paid), ("medical", medical), ("oneoff", one_in - one_out),
                           ("invest", invested)):
                fy[k_] += v_
        net = flow[0] - flow[1]
        if not retired:
            if net >= 0:
                free += net
            else:
                need = -net
                need -= draw(need, True)
                if need > 1e-6:
                    free -= need  # 負債（資金耗盡後的缺口）
                    if depleted is None:
                        depleted = age
        else:
            bucket += net
            if bucket < 0:
                need = -bucket
                bucket = 0.0
                need -= draw(need, False)
                if need > 1e-6:
                    bucket -= need
                    if depleted is None:
                        depleted = age
        policy_sweep()

        if retired or m + 1 >= retire_m:
            if (m + 1 - retire_m) % 12 == 0 and m + 1 < total_m:
                refill(m + 1)

        y_income += net_salary
        y_pension += pension
        y_exp += expense
        y_loan += loan_paid
        y_inv += invested
        y_extra += extra
        y_ins += insurance
        y_med += medical
        y_xexp += extra_exp
        y_oneoff += one_in - one_out
        y_tax += tax_settle

        def prop_value(mm):
            return sum(p_.value * (1 + p_.appreciation / 100) ** (mm / 12)
                       for i, p_ in enumerate(s.properties) if not prop_sold[i])

        if (m + 1) % 12 == 0 or m == total_m - 1:
            pv = prop_value(m + 1)
            liquid = sum(bal) + free + bucket + lp - loan_bal
            nw = liquid + pv
            rows.append(Row(
                age=round(s.current_age + (m + 1) / 12, 2),
                income=y_income, pension_income=y_pension, expense=y_exp, extra_income=y_extra,
                insurance=y_ins, medical=y_med, extra_expense=y_xexp, one_off=y_oneoff, tax_settle=y_tax,
                loan_paid=y_loan, invested=y_inv,
                account_balances=list(bal), free_cash=free, bucket=bucket, lp_balance=lp,
                loan_balance=loan_bal, property_value=pv, net_worth=nw,
                real_net_worth=nw / (infl_m ** (m + 1)), liquid_net_worth=liquid))
            y_income = y_pension = y_exp = y_loan = y_inv = 0.0
            y_extra = y_ins = y_med = y_tax = y_xexp = y_oneoff = 0.0
        if m + 1 == retire_m:
            retire_nw = (sum(bal) + free + bucket + lp - loan_bal + prop_value(m + 1)
                         + s.employer_lump)  # 含退休當月入帳的雇主退休金
            retire_real = retire_nw / (infl_m ** (m + 1))

    if retire_m == 0:
        retire_nw = (sum(a.cash for a in s.accounts) + s.savings_cash + s.lp_balance + s.employer_lump
                     + sum(p_.value for p_ in s.properties))
        retire_real = retire_nw
    if s.lp_enabled and s.lp_claim_age < s.retire_age:
        warnings.append("勞退請領年齡早於退休年齡，已視為退休時才請領")
    n_fy = max(min(12, total_m), 1)
    cashflow = {k: v / n_fy for k, v in fy.items()}
    surplus_now = (cashflow["salary"] + cashflow["extra"] + cashflow["pension"] + cashflow["tax"]
                   + cashflow["oneoff"] - cashflow["living"] - cashflow["xexp"] - cashflow["insurance"]
                   - cashflow["loan"] - cashflow["medical"] - cashflow["invest"])
    if surplus_now < 0 and s.retire_age > s.current_age:
        warnings.append("目前每月現金流為負，不足部分會動用活存/投資帳戶")
    return Result(rows=rows, account_names=[a.name for a in accs],
                  retire_net_worth=retire_nw, retire_real_net_worth=retire_real,
                  depleted_age=depleted, li_monthly=li_pay, lp_monthly=lp_pay,
                  lp_at_claim=lp_at_claim, monthly_surplus_now=surplus_now or 0.0,
                  warnings=warnings, property_sales=property_sales, cashflow=cashflow)


def simulate_scenarios(s: Settings, today: Optional[dt.date] = None) -> dict:
    """悲觀 / 基準 / 樂觀：投資帳戶（含退休金帳戶）報酬率 ∓ scenario_delta 個百分點。"""
    d = s.scenario_delta
    return {"悲觀": simulate(s, today, -d), "基準": simulate(s, today, 0.0), "樂觀": simulate(s, today, d)}
