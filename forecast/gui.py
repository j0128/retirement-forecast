"""tkinter 圖形介面（卡片式版面）。"""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
import os
import sys
import tkinter as tk
from tkinter import filedialog, font as tkfont, messagebox, ttk

from .engine import Account, Loan, Result, Settings, Stage, from_dict, simulate, to_dict

# ---------- 配色 ----------
C = {
    "bg": "#EEF1F6", "card": "#FFFFFF", "line": "#D9DEE7", "navy": "#17304F", "navy2": "#23446B",
    "accent": "#2563EB", "accent_dk": "#1D4ED8", "ok": "#15803D", "warn": "#B45309", "bad": "#B91C1C",
    "text": "#1F2937", "muted": "#6B7280", "stripe": "#F6F8FC", "sel": "#DBE7FF",
    "ok_bg": "#E7F6EC", "bad_bg": "#FDECEC", "warn_bg": "#FEF3E2",
    "c1": "#2563EB", "c2": "#0F9D8A",
}
FONT_PREFS = ["Microsoft JhengHei UI", "Microsoft JhengHei", "PingFang TC", "Noto Sans CJK TC",
              "WenQuanYi Zen Hei", "wenquanyi zen hei", "Segoe UI"]


def settings_path() -> str:
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
        else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "retirement_settings.json")


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


def stage_summary(stages) -> str:
    return "；".join(f"{st.start_age:g}-{st.end_age:g}歲 {st.annual_return:g}%"
                    + (f" 加碼{money(st.monthly_add)}" if st.monthly_add else "")
                    for st in sorted(stages, key=lambda x: x.start_age)) or "（未設定）"


def enable_dpi_awareness():
    if sys.platform.startswith("win"):
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass


def setup_style(root: tk.Tk) -> dict:
    avail = set(tkfont.families(root))
    fam = next((f for f in FONT_PREFS if f in avail), "TkDefaultFont")
    fonts = {
        "base": tkfont.Font(root=root, family=fam, size=10),
        "bold": tkfont.Font(root=root, family=fam, size=10, weight="bold"),
        "small": tkfont.Font(root=root, family=fam, size=9),
        "h1": tkfont.Font(root=root, family=fam, size=17, weight="bold"),
        "h2": tkfont.Font(root=root, family=fam, size=11, weight="bold"),
        "kpi": tkfont.Font(root=root, family=fam, size=19, weight="bold"),
    }
    root.option_add("*Font", fonts["base"])
    root.configure(bg=C["bg"])
    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", background=C["bg"], foreground=C["text"], font=fonts["base"])
    st.configure("TFrame", background=C["bg"])
    st.configure("Card.TFrame", background=C["card"])
    st.configure("TLabel", background=C["bg"], foreground=C["text"])
    st.configure("Card.TLabel", background=C["card"])
    st.configure("Muted.TLabel", background=C["card"], foreground=C["muted"], font=fonts["small"])
    st.configure("Unit.TLabel", background=C["card"], foreground=C["muted"], font=fonts["small"])
    st.configure("TEntry", fieldbackground="#FFFFFF", bordercolor=C["line"], lightcolor=C["line"],
                 darkcolor=C["line"], padding=4)
    st.map("TEntry", bordercolor=[("focus", C["accent"])], lightcolor=[("focus", C["accent"])],
           darkcolor=[("focus", C["accent"])])
    st.configure("TCombobox", fieldbackground="#FFFFFF", bordercolor=C["line"], padding=4,
                 arrowcolor=C["navy"])
    st.configure("TCheckbutton", background=C["card"])
    st.configure("Check.TCheckbutton", background=C["bg"])
    st.configure("TButton", padding=(14, 6), background="#F3F5F9", bordercolor="#B8C2D2",
                 lightcolor="#F3F5F9", darkcolor="#F3F5F9", focuscolor="#F3F5F9", relief="flat")
    st.map("TButton", background=[("active", "#E3EBF9")], bordercolor=[("active", C["accent"])],
           lightcolor=[("active", "#E3EBF9")], darkcolor=[("active", "#E3EBF9")])
    st.configure("Primary.TButton", background=C["accent"], foreground="#FFFFFF", bordercolor=C["accent"],
                 lightcolor=C["accent"], darkcolor=C["accent"], padding=(18, 7), font=fonts["bold"])
    st.map("Primary.TButton", background=[("active", C["accent_dk"]), ("pressed", C["accent_dk"])],
           lightcolor=[("active", C["accent_dk"])], darkcolor=[("active", C["accent_dk"])],
           foreground=[("active", "#FFFFFF")])
    st.configure("Small.TButton", padding=(10, 4), font=fonts["small"])
    st.configure("TNotebook", background=C["bg"], borderwidth=0, tabmargins=(0, 0, 0, 0))
    st.configure("TNotebook.Tab", background="#DCE2EC", foreground=C["muted"], padding=(18, 9),
                 borderwidth=0, font=fonts["bold"])
    st.map("TNotebook.Tab", background=[("selected", C["card"]), ("active", "#E9EDF4")],
           foreground=[("selected", C["navy"])])
    st.configure("Treeview", background="#FFFFFF", fieldbackground="#FFFFFF", rowheight=28,
                 bordercolor=C["line"], borderwidth=0, font=fonts["base"])
    st.map("Treeview", background=[("selected", C["sel"])], foreground=[("selected", C["navy"])])
    st.configure("Treeview.Heading", background=C["navy"], foreground="#FFFFFF", relief="flat",
                 padding=(6, 7), font=fonts["bold"])
    st.map("Treeview.Heading", background=[("active", C["navy2"])])
    st.configure("Vertical.TScrollbar", background="#C9D1DE", troughcolor=C["bg"], bordercolor=C["bg"],
                 arrowcolor=C["navy"])
    st.configure("Horizontal.TScrollbar", background="#C9D1DE", troughcolor=C["bg"], bordercolor=C["bg"],
                 arrowcolor=C["navy"])
    return fonts


def center_on(win: tk.Toplevel, parent: tk.Misc):
    win.update_idletasks()
    w, h = win.winfo_width(), win.winfo_height()
    x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - h) // 3
    win.geometry(f"+{max(x, 0)}+{max(y, 0)}")


class Card(tk.Frame):
    """白底卡片：標題 + 多欄位表單。"""

    def __init__(self, parent, title, fonts, hint=None):
        super().__init__(parent, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
        self.fonts = fonts
        self.row = 0
        bar = tk.Frame(self, bg=C["card"])
        bar.grid(row=0, column=0, columnspan=3, sticky="ew", padx=16, pady=(12, 2))
        tk.Frame(bar, bg=C["accent"], width=4, height=16).pack(side="left", padx=(0, 8))
        tk.Label(bar, text=title, bg=C["card"], fg=C["navy"], font=fonts["h2"]).pack(side="left")
        self.row = 1
        if hint:
            ttk.Label(self, text=hint, style="Muted.TLabel", wraplength=420, justify="left").grid(
                row=self.row, column=0, columnspan=3, sticky="w", padx=16, pady=(0, 4))
            self.row += 1
        self.columnconfigure(1, weight=1)

    def field(self, label, var, unit="", width=16, widget=None):
        ttk.Label(self, text=label, style="Card.TLabel").grid(row=self.row, column=0, sticky="w",
                                                              padx=(16, 10), pady=5)
        w = widget or ttk.Entry(self, textvariable=var, width=width, justify="right")
        w.grid(row=self.row, column=1, sticky="e", pady=5)
        ttk.Label(self, text=unit, style="Unit.TLabel", width=7).grid(row=self.row, column=2, sticky="w",
                                                                      padx=(6, 14))
        self.row += 1
        return w

    def widget(self, w, **kw):
        w.grid(row=self.row, column=0, columnspan=3, sticky=kw.pop("sticky", "w"),
               padx=16, pady=kw.pop("pady", 6), **kw)
        self.row += 1
        return w

    def pad(self):
        tk.Frame(self, bg=C["card"], height=8).grid(row=self.row, column=0)


class FormDialog(tk.Toplevel):
    """通用欄位輸入對話框。fields: [(key, label, kind, default, choices)]"""

    def __init__(self, parent, title, fields):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=C["card"])
        self.transient(parent)
        self.resizable(False, False)
        self.result = None
        self.vars = {}
        self.fields = fields
        body = ttk.Frame(self, style="Card.TFrame")
        body.pack(padx=20, pady=(16, 6))
        for r, (key, label, kind, default, *rest) in enumerate(fields):
            ttk.Label(body, text=label, style="Card.TLabel").grid(row=r, column=0, sticky="w", padx=(0, 14), pady=5)
            if kind == "choice":
                var = tk.StringVar(value=default)
                w = ttk.Combobox(body, textvariable=var, values=rest[0], state="readonly", width=26)
            else:
                var = tk.StringVar(value=f"{default:g}" if kind == "num" else str(default))
                w = ttk.Entry(body, textvariable=var, width=28, justify="right" if kind == "num" else "left")
            w.grid(row=r, column=1, pady=5)
            self.vars[key] = var
        bar = ttk.Frame(self, style="Card.TFrame")
        bar.pack(fill="x", padx=20, pady=(8, 16))
        ttk.Button(bar, text="確定", style="Primary.TButton", command=self._ok).pack(side="right")
        ttk.Button(bar, text="取消", command=self.destroy).pack(side="right", padx=8)
        self.bind("<Return>", lambda e: self._ok())
        self.bind("<Escape>", lambda e: self.destroy())
        center_on(self, parent)
        self.grab_set()
        self.wait_window()

    def _ok(self):
        out = {}
        try:
            for key, label, kind, *_ in self.fields:
                raw = self.vars[key].get().strip()
                out[key] = float(raw.replace(",", "") or 0) if kind == "num" else raw
        except ValueError:
            messagebox.showerror("輸入錯誤", "數字欄位請輸入數字", parent=self)
            return
        self.result = out
        self.destroy()


class StageEditor(tk.Toplevel):
    """編輯投資時間段（以年齡計）。show_add=False 時隱藏每月增額（退休金帳戶用）。"""

    def __init__(self, parent, title, stages, name=None, cash=None, show_add=True):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=C["card"])
        self.transient(parent)
        self.show_add = show_add
        self.stages = [Stage(**vars(st)) for st in stages]
        self.result = None
        self.name_var = tk.StringVar(value=name or "")
        self.cash_var = tk.StringVar(value=f"{cash:,.0f}" if cash is not None else "")
        body = ttk.Frame(self, style="Card.TFrame")
        body.pack(padx=20, pady=(16, 4), fill="both")
        r = 0
        if name is not None:
            for label, var, unit in (("帳戶名稱", self.name_var, ""), ("目前現金/本金", self.cash_var, "NT$")):
                ttk.Label(body, text=label, style="Card.TLabel").grid(row=r, column=0, sticky="w", pady=5)
                ttk.Entry(body, textvariable=var, width=26,
                          justify="left" if unit == "" else "right").grid(row=r, column=1, sticky="w", padx=10)
                ttk.Label(body, text=unit, style="Unit.TLabel").grid(row=r, column=2, sticky="w")
                r += 1
        ttk.Label(body, text="投資時間段", style="Card.TLabel", font=tkfont.nametofont("TkDefaultFont")).grid(
            row=r, column=0, columnspan=3, sticky="w", pady=(10, 4))
        cols = ("start", "end", "ret") + (("add",) if show_add else ())
        heads = ("起始年齡", "結束年齡", "年均報酬 %") + (("每月增額 NT$",) if show_add else ())
        self.tree = ttk.Treeview(body, columns=cols, show="headings", height=6, selectmode="browse")
        for c, h in zip(cols, heads):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=115, anchor="center")
        self.tree.grid(row=r + 1, column=0, columnspan=3, sticky="ew")
        self.tree.bind("<Double-1>", lambda e: self.edit())
        bar = ttk.Frame(body, style="Card.TFrame")
        bar.grid(row=r + 2, column=0, columnspan=3, sticky="w", pady=8)
        for text, cmd in (("＋ 新增時間段", self.add), ("編輯", self.edit), ("刪除", self.delete)):
            ttk.Button(bar, text=text, style="Small.TButton", command=cmd).pack(side="left", padx=(0, 6))
        ttk.Label(body, style="Muted.TLabel", justify="left", wraplength=440, text=(
            "時間段含起始、不含結束年齡。最後一段結束後沿用最後一段的報酬率，並停止加碼。"
            "每月增額僅在退休前有效。")).grid(row=r + 3, column=0, columnspan=3, sticky="w")
        ok = ttk.Frame(self, style="Card.TFrame")
        ok.pack(fill="x", padx=20, pady=(8, 16))
        ttk.Button(ok, text="確定", style="Primary.TButton", command=self._ok).pack(side="right")
        ttk.Button(ok, text="取消", command=self.destroy).pack(side="right", padx=8)
        self._refresh()
        center_on(self, parent)
        self.grab_set()
        self.wait_window()

    def _refresh(self):
        self.stages.sort(key=lambda x: x.start_age)
        self.tree.delete(*self.tree.get_children())
        for i, st in enumerate(self.stages):
            vals = [f"{st.start_age:g}", f"{st.end_age:g}", f"{st.annual_return:g}"]
            if self.show_add:
                vals.append(money(st.monthly_add))
            self.tree.insert("", "end", values=vals, tags=("odd" if i % 2 else "even",))
        self.tree.tag_configure("odd", background=C["stripe"])

    def _dialog(self, st):
        fields = [("start_age", "起始年齡", "num", st.start_age), ("end_age", "結束年齡", "num", st.end_age),
                  ("annual_return", "年均報酬率 %", "num", st.annual_return)]
        if self.show_add:
            fields.append(("monthly_add", "每月增額 NT$", "num", st.monthly_add))
        d = FormDialog(self, "投資時間段", fields)
        if not d.result:
            return None
        r = d.result
        if r["end_age"] <= r["start_age"]:
            messagebox.showerror("輸入錯誤", "結束年齡需大於起始年齡", parent=self)
            return None
        return Stage(**{"monthly_add": 0.0, **r})

    def add(self):
        last = max(self.stages, key=lambda x: x.end_age) if self.stages else None
        st = self._dialog(Stage(last.end_age if last else 0.0, (last.end_age + 10) if last else 120.0,
                                last.annual_return if last else 5.0, 0.0))
        if st:
            self.stages.append(st)
            self._refresh()

    def edit(self):
        sel = self.tree.selection()
        if sel:
            i = self.tree.index(sel[0])
            st = self._dialog(self.stages[i])
            if st:
                self.stages[i] = st
                self._refresh()

    def delete(self):
        sel = self.tree.selection()
        if sel:
            del self.stages[self.tree.index(sel[0])]
            self._refresh()

    def _ok(self):
        try:
            cash = float(self.cash_var.get().replace(",", "") or 0)
        except ValueError:
            messagebox.showerror("輸入錯誤", "現金/本金請輸入數字", parent=self)
            return
        self.result = {"name": self.name_var.get().strip() or "投資帳戶", "cash": cash, "stages": self.stages}
        self.destroy()


class App(tk.Tk):
    # key: (標籤, 單位)；單位以 "NT$" 開頭者視為金額（自動加千分位）
    F = {
        "current_age": ("目前年齡", "歲"), "retire_age": ("預期退休年齡", "歲"),
        "life_expectancy": ("預期壽命（試算到幾歲）", "歲"),
        "monthly_income": ("月均收入（稅前）", "NT$/月"), "income_growth": ("每年調薪", "%"),
        "income_tax_rate": ("所得稅有效稅率", "%"),
        "monthly_expense": ("目前每月生活支出（今日幣值）", "NT$/月"),
        "retire_expense": ("退休後每月生活支出（今日幣值）", "NT$/月"),
        "inflation": ("通膨率", "%/年"),
        "bucket_amount": ("每年年初補足金額（今日幣值）", "NT$"),
        "savings_cash": ("活存現金（未投入）", "NT$"), "savings_rate": ("活存年利率", "%"),
        "gains_tax_rate": ("投資獲利稅率", "%"),
        "lp_wage": ("提繳工資（0 = 取月收入）", "NT$/月"), "lp_wage_cap": ("提繳工資上限", "NT$/月"),
        "lp_employer_pct": ("雇主/學校提繳", "%"), "lp_self_pct": ("個人提繳（自提）", "%"),
        "lp_balance": ("專戶現有餘額", "NT$"), "lp_return": ("專戶年收益率（累積/月領期）", "%"),
        "lp_claim_age": ("請領年齡（不早於退休；私校可退休即領）", "歲"),
        "employer_lump": ("退休時一次領（名目金額）", "NT$"),
        "li_avg_wage": ("平均月投保薪資", "NT$/月"), "li_years_now": ("目前已投保年資", "年"),
        "li_claim_age": ("請領年齡（60~70）", "歲"),
        "li_manual_monthly": ("直接輸入預估月領（>0 則採用）", "NT$/月"),
    }

    def __init__(self):
        enable_dpi_awareness()
        super().__init__()
        self.title("退休收益預測")
        self.geometry("1200x860")
        self.minsize(1040, 700)
        self.fonts = setup_style(self)
        self.s = Settings()
        self.result: Result | None = None
        self.vars: dict[str, tk.Variable] = {}
        self.show_real = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="填好資料後按「開始試算」")
        self._chart = None
        self._build()
        self._load_auto()

    # ---------- 版面 ----------
    def _build(self):
        head = tk.Frame(self, bg=C["navy"])
        head.pack(fill="x")
        tk.Label(head, text="退休收益預測", bg=C["navy"], fg="#FFFFFF", font=self.fonts["h1"]).pack(
            side="left", padx=(22, 10), pady=12)
        tk.Label(head, text="資產 · 現金流 · 勞退勞保 · 退休生活費", bg=C["navy"], fg="#9FB3CF",
                 font=self.fonts["small"]).pack(side="left", pady=(8, 0))
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=18, pady=(12, 6))
        ttk.Button(bar, text="▶  開始試算", style="Primary.TButton", command=self.calculate).pack(side="left")
        ttk.Button(bar, text="儲存設定", command=self.save_as).pack(side="left", padx=(14, 6))
        ttk.Button(bar, text="載入設定", command=self.load_from).pack(side="left", padx=6)
        ttk.Button(bar, text="匯出 CSV", command=self.export_csv).pack(side="left", padx=6)
        ttk.Checkbutton(bar, text="以今日購買力（扣除通膨）顯示", style="Check.TCheckbutton",
                        variable=self.show_real, command=self._render).pack(side="right")

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=18, pady=(4, 0))
        tabs = {}
        for key, name in (("basic", "  基本資料  "), ("acc", "  投資帳戶  "), ("loan", "  房貸 / 貸款  "),
                          ("pen", "  退休金 / 勞保  "), ("res", "  試算結果  ")):
            f = tk.Frame(self.nb, bg=C["bg"])
            self.nb.add(f, text=name)
            tabs[key] = f
        self.tab_res = tabs["res"]
        self._build_basic(tabs["basic"])
        self._build_pension(tabs["pen"])
        self.acc_tree = self._list_tab(
            tabs["acc"], ("name", "cash", "stages"), ("帳戶名稱", "現金/本金 NT$", "投資時間段（年齡 / 報酬 / 加碼）"),
            self.add_account, self.edit_account, self.del_account, reorder=self.move_account,
            note="每個帳戶可設多個投資時間段；退休後依清單順序由上而下提領（可用「上移 / 下移」調整）。",
            widths=(180, 140, 640))
        self.acc_tree.column("cash", anchor="e")
        self.acc_tree.column("stages", anchor="w")
        self.loan_tree = self._list_tab(
            tabs["loan"], ("name", "mode", "pay", "start", "end"),
            ("名稱", "方式", "每月扣款 / 本金 NT$", "起（YYYY-MM）", "迄（YYYY-MM）"),
            self.add_loan, self.edit_loan, self.del_loan,
            note="固定月扣款：直接輸入每月金額；本息平均攤還：輸入本金與利率，自動算出每月扣款與餘額。",
            widths=(180, 220, 180, 150, 150))
        self.loan_tree.column("pay", anchor="e")
        self._build_results(self.tab_res)
        tk.Label(self, textvariable=self.status, bg=C["navy"], fg="#C7D4E8", anchor="w", padx=18, pady=5,
                 font=self.fonts["small"]).pack(fill="x", side="bottom", pady=(8, 0))

    def _var(self, key, kind="str"):
        v = tk.BooleanVar() if kind == "bool" else tk.StringVar()
        self.vars[key] = v
        return v

    def _money_entry(self, card, key):
        label, unit = self.F[key]
        w = card.field(label, self._var(key), unit)
        if unit.startswith("NT$"):
            w.bind("<FocusOut>", lambda e, k=key: self._fmt_money(k))
        return w

    def _fmt_money(self, key):
        try:
            v = float(self.vars[key].get().replace(",", "") or 0)
        except ValueError:
            return
        self.vars[key].set(f"{v:,.0f}")

    def _grid_cards(self, parent, cards, cols=2):
        for c in range(cols):
            parent.columnconfigure(c, weight=1, uniform="col")
        for i, card in enumerate(cards):
            card.grid(row=i // cols, column=i % cols, sticky="nsew", padx=(0 if i % cols == 0 else 8, 8 if i % cols == 0 else 0),
                      pady=(0, 10))

    def _build_basic(self, p):
        p.configure(padx=2, pady=12)
        c1 = Card(p, "個人與收入", self.fonts)
        for k in ("current_age", "retire_age", "life_expectancy", "monthly_income", "income_growth",
                  "income_tax_rate"):
            self._money_entry(c1, k)
        c1.pad()
        c2 = Card(p, "支出與通膨", self.fonts)
        for k in ("monthly_expense", "retire_expense", "inflation"):
            self._money_entry(c2, k)
        c2.pad()
        c3 = Card(p, "現金與投資稅", self.fonts)
        for k in ("savings_cash", "savings_rate", "gains_tax_rate"):
            self._money_entry(c3, k)
        c3.pad()
        c4 = Card(p, "退休後生活費帳戶", self.fonts,
                  hint="退休後每年年初，依投資帳戶清單順序提領，把此帳戶補足到設定金額；"
                       "年金與退休金月領先進此帳戶，生活費與貸款由此支出。")
        self._money_entry(c4, "bucket_amount")
        c4.pad()
        self._grid_cards(p, [c1, c2, c3, c4])

    def _build_pension(self, p):
        p.configure(padx=2, pady=12)
        c1 = Card(p, "退休金專戶（勞退新制 / 私校退撫儲金）", self.fonts,
                  hint="提繳比例請依薪資單設定。一次領會在請領時轉入「退休金帳戶」繼續投資。")
        self.vars["lp_enabled"] = tk.BooleanVar()
        c1.widget(ttk.Checkbutton(c1, text="計入退休金專戶", variable=self.vars["lp_enabled"]), pady=(2, 2))
        for k in ("lp_wage", "lp_wage_cap", "lp_employer_pct", "lp_self_pct", "lp_balance", "lp_return",
                  "lp_claim_age"):
            self._money_entry(c1, k)
        self.vars["lp_lump_sum"] = tk.StringVar()
        c1.field("領取方式", None, "", widget=ttk.Combobox(c1, textvariable=self.vars["lp_lump_sum"],
                                                         values=["月領", "一次領"], state="readonly", width=14))
        c1.widget(ttk.Button(c1, text="設定「退休金帳戶」投資階段", style="Small.TButton",
                             command=self.edit_lump_stages), pady=(4, 12))
        c2 = Card(p, "雇主另給的退休金", self.fonts,
                  hint="退休當月一次領，轉入「退休金帳戶」，與專戶一次領的金額合併投資。填 0 表示沒有。")
        self._money_entry(c2, "employer_lump")
        c2.pad()
        c3 = Card(p, "勞保老年年金", self.fonts,
                  hint="公式：年資 ×（投保薪資 × 0.775% + 3,000）與（投保薪資 × 1.55%）取高者；"
                       "提前/延後每年 ∓4%（最多 5 年）。年資 = 目前年資 + 退休前繼續投保年數。"
                       "投保薪資上限以現行規定為準。")
        self.vars["li_enabled"] = tk.BooleanVar()
        c3.widget(ttk.Checkbutton(c3, text="計入勞保老年年金（預設 65 歲起領）", variable=self.vars["li_enabled"]),
                  pady=(2, 2))
        for k in ("li_avg_wage", "li_years_now", "li_claim_age", "li_manual_monthly"):
            self._money_entry(c3, k)
        c3.pad()
        right = tk.Frame(p, bg=C["bg"])
        right.columnconfigure(0, weight=1)
        for c in (0, 1):
            p.columnconfigure(c, weight=1, uniform="col")
        c1.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 8), pady=(0, 10))
        c2.grid(row=0, column=1, sticky="new", padx=(8, 0), pady=(0, 10))
        c3.grid(row=1, column=1, sticky="new", padx=(8, 0), pady=(0, 10))

    def _list_tab(self, parent, cols, heads, add, edit, delete, reorder=None, note="", widths=None):
        parent.configure(padx=2, pady=12)
        card = tk.Frame(parent, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
        card.pack(fill="both", expand=True, pady=(0, 10))
        if note:
            ttk.Label(card, text=note, style="Muted.TLabel").pack(anchor="w", padx=16, pady=(12, 4))
        tree = ttk.Treeview(card, columns=cols, show="headings", height=9, selectmode="browse")
        for i, (c, h) in enumerate(zip(cols, heads)):
            tree.heading(c, text=h)
            tree.column(c, width=(widths[i] if widths else 150), anchor="center")
        tree.tag_configure("odd", background=C["stripe"])
        tree.pack(fill="both", expand=True, padx=16, pady=6)
        bar = ttk.Frame(card, style="Card.TFrame")
        bar.pack(fill="x", padx=16, pady=(2, 14))
        ttk.Button(bar, text="＋ 新增", style="Primary.TButton", command=add).pack(side="left")
        ttk.Button(bar, text="編輯", command=edit).pack(side="left", padx=6)
        ttk.Button(bar, text="刪除", command=delete).pack(side="left")
        if reorder:
            ttk.Button(bar, text="▲ 上移", command=lambda: reorder(-1)).pack(side="left", padx=(24, 6))
            ttk.Button(bar, text="▼ 下移", command=lambda: reorder(1)).pack(side="left")
        tree.bind("<Double-1>", lambda e: edit())
        return tree

    def _build_results(self, p):
        p.configure(padx=2, pady=12)
        self.kpi_row = tk.Frame(p, bg=C["bg"])
        self.kpi_row.pack(fill="x")
        self.kpis = []
        for i in range(4):
            self.kpi_row.columnconfigure(i, weight=1, uniform="k")
            f = tk.Frame(self.kpi_row, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
            f.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0 if i == 3 else 6))
            t = tk.Label(f, text="", bg=C["card"], fg=C["muted"], font=self.fonts["small"], anchor="w")
            v = tk.Label(f, text="—", bg=C["card"], fg=C["navy"], font=self.fonts["kpi"], anchor="w")
            s = tk.Label(f, text="", bg=C["card"], fg=C["muted"], font=self.fonts["small"], anchor="w",
                         justify="left", wraplength=250)
            t.pack(fill="x", padx=14, pady=(10, 0))
            v.pack(fill="x", padx=14)
            s.pack(fill="x", padx=14, pady=(0, 10))
            self.kpis.append((f, t, v, s))
        self.alert = tk.Label(p, text="", bg=C["bg"], fg=C["warn"], anchor="w", justify="left",
                              font=self.fonts["small"], wraplength=1080)
        self.alert.pack(fill="x", pady=(6, 0))
        chart_card = tk.Frame(p, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
        chart_card.pack(fill="x", pady=(6, 8))
        self.canvas = tk.Canvas(chart_card, height=250, bg=C["card"], highlightthickness=0)
        self.canvas.pack(fill="x", padx=6, pady=6)
        self.canvas.bind("<Configure>", lambda e: self._draw_chart())
        self.canvas.bind("<Motion>", self._hover)
        self.canvas.bind("<Leave>", lambda e: self.canvas.delete("hover"))
        tbl = tk.Frame(p, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
        tbl.pack(fill="both", expand=True)
        self.res_tree = ttk.Treeview(tbl, show="headings", height=8)
        ys = ttk.Scrollbar(tbl, orient="vertical", command=self.res_tree.yview)
        xs = ttk.Scrollbar(tbl, orient="horizontal", command=self.res_tree.xview)
        self.res_tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        ys.pack(side="right", fill="y")
        xs.pack(side="bottom", fill="x")
        self.res_tree.pack(fill="both", expand=True)
        self.res_tree.tag_configure("odd", background=C["stripe"])
        self.res_tree.tag_configure("retire", background="#FFF4D6")

    # ---------- 資料 <-> 表單 ----------
    def _to_form(self):
        s = self.s
        for key, v in self.vars.items():
            val = getattr(s, key)
            if key == "lp_lump_sum":
                v.set("一次領" if val else "月領")
            elif isinstance(v, tk.BooleanVar):
                v.set(bool(val))
            elif key in self.F and self.F[key][1].startswith("NT$"):
                v.set(f"{val:,.0f}")
            else:
                v.set(f"{val:g}" if isinstance(val, float) else str(val))
        self._refresh_lists()

    def _from_form(self) -> Settings:
        s = self.s
        for key, v in self.vars.items():
            if key == "lp_lump_sum":
                s.lp_lump_sum = v.get() == "一次領"
            elif isinstance(v, tk.BooleanVar):
                setattr(s, key, bool(v.get()))
            else:
                raw = v.get().strip().replace(",", "")
                try:
                    setattr(s, key, float(raw or 0))
                except ValueError:
                    raise ValueError(f"「{self.F.get(key, (key,))[0]}」不是有效數字：{raw}")
        return s

    def _refresh_lists(self):
        self.acc_tree.delete(*self.acc_tree.get_children())
        for i, a in enumerate(self.s.accounts):
            self.acc_tree.insert("", "end", values=(a.name, money(a.cash), "    " + stage_summary(a.stages)),
                                 tags=("odd" if i % 2 else "even",))
        self.loan_tree.delete(*self.loan_tree.get_children())
        for i, l in enumerate(self.s.loans):
            if l.mode == "amort":
                mode, amt = f"本息平均攤還 {l.annual_rate:g}%", money(l.principal)
            else:
                mode, amt = "固定月扣款", money(l.monthly_payment)
            end = l.end or f"(+{l.years:g} 年)"
            self.loan_tree.insert("", "end", values=(l.name, mode, amt, l.start, end),
                                  tags=("odd" if i % 2 else "even",))

    # ---------- 投資帳戶 / 貸款編輯 ----------
    def _sel(self, tree):
        sel = tree.selection()
        return tree.index(sel[0]) if sel else None

    def _acc_dialog(self, a: Account | None):
        a = a or Account(name=f"投資帳戶 {len(self.s.accounts) + 1}",
                         stages=[Stage(self.s.current_age, self.s.current_age + 20, 5.0, 0.0),
                                 Stage(self.s.current_age + 20, 120.0, 4.0, 0.0)])
        d = StageEditor(self, "投資帳戶", a.stages, name=a.name, cash=a.cash)
        return Account(**d.result) if d.result else None

    def add_account(self):
        a = self._acc_dialog(None)
        if a:
            self.s.accounts.append(a)
            self._refresh_lists()

    def edit_account(self):
        i = self._sel(self.acc_tree)
        if i is not None:
            a = self._acc_dialog(self.s.accounts[i])
            if a:
                self.s.accounts[i] = a
                self._refresh_lists()

    def del_account(self):
        i = self._sel(self.acc_tree)
        if i is not None:
            del self.s.accounts[i]
            self._refresh_lists()

    def move_account(self, delta):
        i = self._sel(self.acc_tree)
        if i is None or not 0 <= i + delta < len(self.s.accounts):
            return
        accs = self.s.accounts
        accs[i], accs[i + delta] = accs[i + delta], accs[i]
        self._refresh_lists()
        self.acc_tree.selection_set(self.acc_tree.get_children()[i + delta])

    def edit_lump_stages(self):
        d = StageEditor(self, "退休金帳戶投資階段", self.s.lump_stages, show_add=False)
        if d.result:
            self.s.lump_stages = d.result["stages"]
            self.status.set("已更新退休金帳戶的投資階段")

    def _loan_dialog(self, l: Loan | None):
        l = l or Loan(start=dt.date.today().strftime("%Y-%m"))
        names = ["固定月扣款", "本息平均攤還（輸入本金與利率）"]
        d = FormDialog(self, "房貸/貸款", [
            ("name", "名稱", "text", l.name),
            ("mode", "計算方式", "choice", names[1] if l.mode == "amort" else names[0], names),
            ("monthly_payment", "每月扣款 NT$（固定月扣款用）", "num", l.monthly_payment),
            ("principal", "原貸款金額 NT$（攤還用）", "num", l.principal),
            ("annual_rate", "年利率 %（攤還用）", "num", l.annual_rate),
            ("start", "起始年月 YYYY-MM", "text", l.start),
            ("end", "結束年月 YYYY-MM（含）", "text", l.end),
            ("years", "或貸款年限（結束年月留空時，攤還用）", "num", l.years)])
        if not d.result:
            return None
        r = d.result
        r["mode"] = "amort" if r["mode"] == names[1] else "fixed"
        return Loan(**r)

    def add_loan(self):
        l = self._loan_dialog(None)
        if l:
            self.s.loans.append(l)
            self._refresh_lists()

    def edit_loan(self):
        i = self._sel(self.loan_tree)
        if i is not None:
            l = self._loan_dialog(self.s.loans[i])
            if l:
                self.s.loans[i] = l
                self._refresh_lists()

    def del_loan(self):
        i = self._sel(self.loan_tree)
        if i is not None:
            del self.s.loans[i]
            self._refresh_lists()

    # ---------- 計算與顯示 ----------
    def calculate(self):
        try:
            self._from_form()
            self.result = simulate(self.s)
        except ValueError as e:
            messagebox.showerror("無法試算", str(e))
            return
        self._save_auto()
        self.nb.select(self.tab_res)
        self._render()
        self.status.set(f"試算完成 · {dt.datetime.now():%H:%M:%S} · 設定已自動儲存")

    def _set_kpi(self, i, title, value, sub, color=None):
        f, t, v, s = self.kpis[i]
        t.config(text=title)
        v.config(text=value, fg=color or C["navy"])
        s.config(text=sub)

    def _render(self):
        r = self.result
        if not r:
            return
        s = self.s
        end = r.rows[-1]
        self._set_kpi(0, f"{s.retire_age:g} 歲退休時淨資產", f"NT$ {short_money(r.retire_net_worth)}",
                      f"今日購買力 NT$ {short_money(r.retire_real_net_worth)}")
        self._set_kpi(1, f"{s.life_expectancy:g} 歲時淨資產", f"NT$ {short_money(end.net_worth)}",
                      f"今日購買力 NT$ {short_money(end.real_net_worth)}",
                      C["bad"] if end.net_worth < 0 else None)
        if r.depleted_age:
            self._set_kpi(2, "資產狀態", f"約 {r.depleted_age:.1f} 歲耗盡", "之後生活費出現缺口，需調整計畫", C["bad"])
        else:
            self._set_kpi(2, "資產狀態", f"可支撐至 {s.life_expectancy:g} 歲", "全程現金流與資產皆為正", C["ok"])
        monthly = r.li_monthly + (0 if s.lp_lump_sum else r.lp_monthly)
        parts = [f"勞保年金 {money(r.li_monthly)}"]
        if s.lp_enabled:
            parts.append(f"退休金一次領 {money(r.lp_at_claim)}（轉入退休金帳戶）" if s.lp_lump_sum
                         else f"退休金月領 {money(r.lp_monthly)}")
        if s.employer_lump > 0:
            parts.append(f"雇主退休金 {money(s.employer_lump)}")
        self._set_kpi(3, "退休後固定月收入", f"NT$ {money(monthly)}", "\n".join(parts))
        msgs = [f"目前每月現金流（收入 − 支出 − 貸款 − 投資）：NT$ {money(r.monthly_surplus_now)}"] + \
               [f"⚠ {w}" for w in r.warnings]
        self.alert.config(text="    ".join(msgs), fg=C["bad"] if r.monthly_surplus_now < 0 else C["muted"])

        names = r.account_names
        cols = ["age", "income", "pension", "expense", "loan", "invest"] + \
               [f"a{i}" for i in range(len(names))] + ["free", "bucket", "lp", "debt", "nw", "real"]
        heads = ["年齡", "稅後薪資", "年金/退休金月領", "生活支出", "貸款支出", "新增投資"] + names + \
                ["活存/現金", "生活費帳戶", "退休金專戶", "貸款餘額", "淨資產", "淨資產(今日購買力)"]
        self.res_tree.configure(columns=cols)
        for c, h in zip(cols, heads):
            self.res_tree.heading(c, text=h)
            self.res_tree.column(c, width=118 if c not in ("age",) else 64, anchor="e", stretch=False)
        self.res_tree.column("age", anchor="center")
        self.res_tree.delete(*self.res_tree.get_children())
        for i, x in enumerate(r.rows):
            tags = ["odd" if i % 2 else "even"]
            if abs(x.age - s.retire_age) < 0.01:
                tags.append("retire")
            self.res_tree.insert("", "end", tags=tags, values=[f"{x.age:g}", money(x.income), money(x.pension_income),
                                                               money(x.expense), money(x.loan_paid), money(x.invested)] +
                                 [money(b) for b in x.account_balances] +
                                 [money(x.free_cash), money(x.bucket), money(x.lp_balance), money(x.loan_balance),
                                  money(x.net_worth), money(x.real_net_worth)])
        self._draw_chart()

    # ---------- 圖表 ----------
    def _draw_chart(self):
        c = self.canvas
        c.delete("all")
        self._chart = None
        r = self.result
        w, h = c.winfo_width(), c.winfo_height()
        if not r or not r.rows or w < 50:
            c.create_text(w / 2 if w > 50 else 200, h / 2, text="按「開始試算」後在此顯示淨資產走勢",
                          fill=C["muted"], font=self.fonts["base"])
            return
        L, R, T, B = 78, 24, 34, 34
        rows = r.rows
        ages = [x.age for x in rows]
        nom = [x.net_worth for x in rows]
        real = [x.real_net_worth for x in rows]
        real_first = self.show_real.get()
        main, sub = (real, nom) if real_first else (nom, real)
        main_name, sub_name = ("今日購買力", "名目金額") if real_first else ("名目金額", "今日購買力")
        allv = nom + real + [0]
        ticks = nice_ticks(min(allv), max(allv), 5)
        lo, hi = ticks[0], ticks[-1]
        x0, x1 = ages[0], ages[-1]

        def px(a):
            return L + (a - x0) / max(x1 - x0, 1e-9) * (w - L - R)

        def py(v):
            return T + (hi - v) / (hi - lo) * (h - T - B)
        for tv in ticks:
            c.create_line(L, py(tv), w - R, py(tv), fill="#E8ECF2")
            c.create_text(L - 8, py(tv), text=short_money(tv), anchor="e", fill=C["muted"], font=self.fonts["small"])
        step = 5 if (x1 - x0) > 25 else 2 if (x1 - x0) > 10 else 1
        a = math.ceil(x0 / step) * step
        while a <= x1 + 1e-9:
            c.create_text(px(a), h - B + 14, text=f"{a:g}", fill=C["muted"], font=self.fonts["small"])
            a += step
        c.create_text(w - R, h - 8, text="年齡（歲）", anchor="e", fill=C["muted"], font=self.fonts["small"])
        c.create_line(L, py(0), w - R, py(0), fill="#9AA5B8")
        # 退休 / 耗盡標記
        ra = self.s.retire_age
        if x0 <= ra <= x1:
            c.create_line(px(ra), T - 6, px(ra), h - B, fill="#D97706", dash=(4, 3))
            c.create_text(px(ra) + 5, T - 8, text=f"退休 {ra:g}", anchor="w", fill="#D97706", font=self.fonts["small"])
        if r.depleted_age and x0 <= r.depleted_age <= x1:
            dx = px(r.depleted_age)
            c.create_line(dx, T - 6, dx, h - B, fill=C["bad"], dash=(2, 3))
            c.create_text(dx - 5, T - 8, text=f"耗盡 {r.depleted_age:.0f}", anchor="e", fill=C["bad"],
                          font=self.fonts["small"])
        # 區域填色在最底層，其上依序為次要線（虛線）與主要線（粗線）
        sp = [co for a_, v in zip(ages, sub) for co in (px(a_), py(v))]
        mp = [co for a_, v in zip(ages, main) for co in (px(a_), py(v))]
        if len(mp) >= 4:
            c.create_polygon(*([px(ages[0]), py(0)] + mp + [px(ages[-1]), py(0)]), fill="#DCE8FF", outline="")
        if len(sp) >= 4:
            c.create_line(*sp, fill=C["c2"], width=2, dash=(5, 3))
        if len(mp) >= 4:
            c.create_line(*mp, fill=C["c1"], width=3)
        # 圖例
        lx = L
        for name, color, dash in ((main_name, C["c1"], None), (sub_name, C["c2"], (5, 3))):
            c.create_line(lx, 12, lx + 22, 12, fill=color, width=3 if dash is None else 2, dash=dash)
            c.create_text(lx + 28, 12, text=name, anchor="w", fill=C["text"], font=self.fonts["small"])
            lx += 130
        self._chart = {"px": px, "py": py, "ages": ages, "rows": rows, "L": L, "R": R, "T": T, "B": B,
                       "w": w, "h": h}

    def _hover(self, e):
        c = self.canvas
        c.delete("hover")
        g = self._chart
        if not g or not (g["L"] <= e.x <= g["w"] - g["R"]):
            return
        i = min(range(len(g["ages"])), key=lambda k: abs(g["px"](g["ages"][k]) - e.x))
        row = g["rows"][i]
        x = g["px"](row.age)
        c.create_line(x, g["T"], x, g["h"] - g["B"], fill="#94A3B8", tags="hover")
        for v, color in ((row.net_worth, C["c1"]), (row.real_net_worth, C["c2"])):
            y = g["py"](v)
            c.create_oval(x - 4, y - 4, x + 4, y + 4, fill="#FFFFFF", outline=color, width=2, tags="hover")
        lines = [f"{row.age:g} 歲", f"名目淨資產  {money(row.net_worth)}",
                 f"今日購買力  {money(row.real_net_worth)}", f"貸款餘額  {money(row.loan_balance)}"]
        bw, bh = 188, 18 * len(lines) + 12
        bx = x + 14 if x + 14 + bw < g["w"] - 4 else x - 14 - bw
        by = max(g["T"], min(e.y - bh / 2, g["h"] - g["B"] - bh))
        c.create_rectangle(bx, by, bx + bw, by + bh, fill="#17304F", outline="", tags="hover")
        for k, t in enumerate(lines):
            c.create_text(bx + 10, by + 15 + k * 18, text=t, anchor="w", fill="#FFFFFF",
                          font=self.fonts["bold" if k == 0 else "small"], tags="hover")

    # ---------- 檔案 ----------
    def _save_auto(self):
        try:
            with open(settings_path(), "w", encoding="utf-8") as f:
                json.dump(to_dict(self.s), f, ensure_ascii=False, indent=2)
        except OSError:
            pass

    def _load_auto(self):
        try:
            with open(settings_path(), encoding="utf-8") as f:
                self.s = from_dict(json.load(f))
        except (OSError, ValueError):
            pass
        self._to_form()

    def save_as(self):
        try:
            self._from_form()
        except ValueError as e:
            messagebox.showerror("輸入錯誤", str(e))
            return
        p = filedialog.asksaveasfilename(defaultextension=".json", filetypes=[("JSON", "*.json")])
        if p:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(to_dict(self.s), f, ensure_ascii=False, indent=2)
            self.status.set(f"設定已儲存：{p}")

    def load_from(self):
        p = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if p:
            try:
                with open(p, encoding="utf-8") as f:
                    self.s = from_dict(json.load(f))
            except (OSError, ValueError) as e:
                messagebox.showerror("載入失敗", str(e))
                return
            self._to_form()
            self.status.set(f"已載入設定：{p}")

    def export_csv(self):
        if not self.result:
            messagebox.showinfo("提示", "請先按「開始試算」")
            return
        p = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not p:
            return
        r = self.result
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["年齡", "稅後薪資", "年金/退休金月領", "生活支出", "貸款支出", "新增投資"] +
                       r.account_names + ["活存/現金", "生活費帳戶", "退休金專戶", "貸款餘額", "淨資產",
                                          "淨資產(今日購買力)"])
            for x in r.rows:
                w.writerow([x.age, round(x.income), round(x.pension_income), round(x.expense),
                            round(x.loan_paid), round(x.invested)] +
                           [round(b) for b in x.account_balances] +
                           [round(x.free_cash), round(x.bucket), round(x.lp_balance), round(x.loan_balance),
                            round(x.net_worth), round(x.real_net_worth)])
        self.status.set(f"已匯出 CSV：{p}")


def main():
    App().mainloop()
