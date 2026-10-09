"""tkinter 圖形介面（卡片式版面）。"""
from __future__ import annotations

import csv
import datetime as dt
import json
import math
import os
import sys
import tkinter as tk
import webbrowser
from tkinter import filedialog, font as tkfont, messagebox, ttk

from .engine import (BUCKET, CASH, Account, ExtraExpense, ExtraIncome, Insurance, Loan, OneOff, Policy, Property,
                     Result, Settings, Stage, from_dict, simulate_scenarios, to_dict)
from .fmt import money, nice_ticks, num_str, short_money
from .report import build_report

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
    st.configure("Vertical.TScrollbar", background="#B9C3D3", troughcolor="#E3E8F0", bordercolor="#E3E8F0",
                 arrowcolor=C["navy"], width=16, arrowsize=16)
    st.map("Vertical.TScrollbar", background=[("active", "#8EA0BB")])
    st.configure("Horizontal.TScrollbar", background="#B9C3D3", troughcolor="#E3E8F0", bordercolor="#E3E8F0",
                 arrowcolor=C["navy"], width=16, arrowsize=16)
    st.map("Horizontal.TScrollbar", background=[("active", "#8EA0BB")])
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


class ScrollFrame(tk.Frame):
    """可垂直捲動的頁面容器：內容放在 .inner。"""

    def __init__(self, parent):
        super().__init__(parent, bg=C["bg"])
        self.canvas = tk.Canvas(self, bg=C["bg"], highlightthickness=0)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vbar.set)
        self.vbar.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=C["bg"], padx=18, pady=14)
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.win, width=e.width))

    def scroll(self, units: int):
        if self.inner.winfo_reqheight() > self.canvas.winfo_height():
            self.canvas.yview_scroll(units, "units")

    def to_top(self):
        self.canvas.yview_moveto(0)


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
                var = tk.StringVar(value=num_str(default) if kind == "num" else str(default))
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
        self.cash_var = tk.StringVar(value=num_str(cash) if cash is not None else "")
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
        "salary_net": ("實領月薪", "NT$/月"), "salary_withheld": ("每月預扣所得稅（不含在實領薪水內）", "NT$/月"),
        "income_growth": ("每年調薪", "%"), "income_tax_rate": ("年度所得稅有效稅率（占課稅所得 %）", "%"),
        "bonus_months": ("年終 / 績效獎金（實領月薪的幾個月）", "個月"), "bonus_month": ("獎金發放月份", "月"),
        "medical_start_age": ("醫療費用起算年齡", "歲"), "medical_monthly": ("起算時每月醫療費用（今日幣值）", "NT$/月"),
        "medical_growth": ("醫療費用高於通膨的年增幅", "%/年"),
        "scenario_delta": ("悲觀 / 樂觀：投資報酬率 ∓", "百分點"),
        "monthly_expense": ("目前每月生活支出（今日幣值）", "NT$/月"),
        "retire_expense": ("退休後每月生活支出（今日幣值）", "NT$/月"),
        "inflation": ("通膨率", "%/年"),
        "bucket_amount": ("每年年初補足金額", "NT$"),
        "savings_cash": ("活存現金（未投入）", "NT$"), "savings_rate": ("活存年利率", "%"),
        "gains_tax_rate": ("投資獲利稅率", "%"),
        "lp_monthly_add": ("每月固定提繳金額（>0 則取代下方比例）", "NT$/月"),
        "lp_wage": ("提繳工資（0 = 以實領+預扣稅估算）", "NT$/月"), "lp_wage_cap": ("提繳工資上限", "NT$/月"),
        "lp_employer_pct": ("雇主/學校提繳", "%"), "lp_self_pct": ("個人提繳（自提）", "%"),
        "lp_balance": ("專戶現有餘額", "NT$"), "lp_return": ("專戶年收益率（累積/月領期）", "%"),
        "lp_claim_age": ("請領年齡（不早於退休；私校可退休即領）", "歲"),
        "employer_lump": ("退休時一次領（名目金額）", "NT$"),
        "li_avg_wage": ("平均月投保薪資", "NT$/月"), "li_years_now": ("目前已投保年資", "年"),
        "li_claim_age": ("請領年齡（60~70）", "歲"),
        "li_manual_monthly": ("直接輸入預估月領（>0 則採用）", "NT$/月"),
    }

    NAV = [("basic", "基本資料"), ("income", "收入"), ("expense", "支出"), ("acc", "投資帳戶"),
           ("flow", "資金流向"), ("loan", "房貸 / 貸款"), ("prop", "不動產"), ("ins", "保險"), ("pen", "退休金 / 勞保"),
           ("res", "試算結果")]

    def __init__(self):
        enable_dpi_awareness()
        super().__init__()
        self.title("退休收益預測")
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = min(1440, int(sw * 0.92)), min(960, int(sh * 0.9))
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+{max((sh - h) // 2 - 20, 0)}")
        self.minsize(min(980, w), min(620, h))
        self.fonts = setup_style(self)
        self.s = Settings()
        self.result: Result | None = None
        self.results: dict = {}
        self.vars: dict[str, tk.Variable] = {}
        self.show_real = tk.BooleanVar(value=False)
        self.status = tk.StringVar(value="填好資料後按「開始試算」")
        self._chart = None
        self.pages: dict[str, ScrollFrame] = {}
        self.nav_items: dict = {}
        self.acct_vars: dict[str, tk.StringVar] = {}
        self.acct_combos: list = []
        self.current_page = None
        self._build()
        self.bind_all("<MouseWheel>", self._wheel)
        self.bind_all("<Button-4>", self._wheel)
        self.bind_all("<Button-5>", self._wheel)
        self._load_auto()
        self.show("basic")

    def _wheel(self, e):
        w = e.widget
        if not isinstance(w, tk.Misc) or isinstance(w, (ttk.Treeview, tk.Listbox)):
            return
        num = getattr(e, "num", 0)
        if num == 4:
            units = -3
        elif num == 5:
            units = 3
        else:
            units = -3 if e.delta > 0 else 3
        while w is not None and not isinstance(w, ScrollFrame):
            w = getattr(w, "master", None)
        if w is not None:
            w.scroll(units)

    # ---------- 版面 ----------
    def _build(self):
        head = tk.Frame(self, bg=C["navy"])
        head.pack(fill="x")
        tk.Label(head, text="退休收益預測", bg=C["navy"], fg="#FFFFFF", font=self.fonts["h1"]).pack(
            side="left", padx=(22, 10), pady=12)
        tk.Label(head, text="資產 · 現金流 · 勞退勞保 · 退休生活費", bg=C["navy"], fg="#9FB3CF",
                 font=self.fonts["small"]).pack(side="left", pady=(8, 0))
        tk.Label(self, textvariable=self.status, bg=C["navy"], fg="#C7D4E8", anchor="w", padx=18, pady=5,
                 font=self.fonts["small"]).pack(fill="x", side="bottom")
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True)
        side = tk.Frame(body, bg=C["navy2"], width=190)
        side.pack(side="left", fill="y")
        side.pack_propagate(False)
        tk.Label(side, text="設定項目", bg=C["navy2"], fg="#9FB3CF", font=self.fonts["small"], anchor="w").pack(
            fill="x", padx=18, pady=(16, 6))
        for i, (key, name) in enumerate(self.NAV):
            if key == "res":
                tk.Frame(side, bg="#35557F", height=1).pack(fill="x", padx=14, pady=8)
            row = tk.Frame(side, bg=C["navy2"], cursor="hand2")
            row.pack(fill="x")
            bar = tk.Frame(row, bg=C["navy2"], width=4)
            bar.pack(side="left", fill="y")
            num = "▶" if key == "res" else f"{i + 1}"
            lab = tk.Label(row, text=f"  {num}   {name}", bg=C["navy2"], fg="#DDE6F3", anchor="w",
                           font=self.fonts["bold"] if key == "res" else self.fonts["base"], pady=9)
            lab.pack(side="left", fill="x", expand=True)
            self.nav_items[key] = (row, bar, lab)
            for wdg in (row, lab, bar):
                wdg.bind("<Button-1>", lambda e, k=key: self.show(k))
                wdg.bind("<Enter>", lambda e, k=key: self._nav_hover(k, True))
                wdg.bind("<Leave>", lambda e, k=key: self._nav_hover(k, False))
        main = tk.Frame(body, bg=C["bg"])
        main.pack(side="left", fill="both", expand=True)
        bar = ttk.Frame(main)
        bar.pack(fill="x", padx=18, pady=(12, 4))
        ttk.Button(bar, text="▶  開始試算", style="Primary.TButton", command=self.calculate).pack(side="left")
        for text, cmd in (("儲存設定", self.save_as), ("載入設定", self.load_from), ("匯出 CSV", self.export_csv),
                          ("匯出報告", self.export_report)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=(10, 0))
        ttk.Checkbutton(bar, text="以今日購買力（扣除通膨）顯示", style="Check.TCheckbutton",
                        variable=self.show_real, command=self._on_basis).pack(side="right")
        stack = tk.Frame(main, bg=C["bg"])
        stack.pack(fill="both", expand=True)
        stack.rowconfigure(0, weight=1)
        stack.columnconfigure(0, weight=1)
        for key, _ in self.NAV:
            sf = ScrollFrame(stack)
            sf.grid(row=0, column=0, sticky="nsew")
            self.pages[key] = sf
        self._build_basic(self.pages["basic"].inner)
        self._build_income(self.pages["income"].inner)
        self._build_expense(self.pages["expense"].inner)
        self.acc_tree = self._list_card(
            self.pages["acc"].inner, "投資帳戶", ("name", "cash", "stages"),
            ("帳戶名稱", "現金/本金 NT$", "投資時間段（年齡 / 報酬 / 加碼）"),
            self.add_account, self.edit_account, self.del_account, reorder=self.move_account,
            note="每個帳戶可設多個投資時間段；退休後依清單順序由上而下提領（可用「上移 / 下移」調整）。",
            widths=(180, 140, 640), height=12)
        self.acc_tree.column("cash", anchor="e")
        self.acc_tree.column("stages", anchor="w")
        self._build_flow(self.pages["flow"].inner)
        self.loan_tree = self._list_card(
            self.pages["loan"].inner, "房貸 / 貸款", ("name", "mode", "pay", "start", "end", "acct"),
            ("名稱", "方式", "每月扣款 / 本金 NT$", "起（YYYY-MM）", "迄（YYYY-MM）", "還款帳戶"),
            self.add_loan, self.edit_loan, self.del_loan,
            note="固定月扣款：直接輸入每月金額；本息平均攤還：輸入本金與利率，自動算出每月扣款與餘額。",
            widths=(160, 200, 170, 130, 130, 150), height=12)
        self.loan_tree.column("pay", anchor="e")
        self.prop_tree = self._list_card(
            self.pages["prop"].inner, "不動產", ("name", "value", "buy", "g", "sell", "loan"),
            ("名稱", "目前市值 NT$", "購入價 NT$", "年增值率 %", "出售年齡", "出售時還清貸款"),
            self.add_prop, self.edit_prop, self.del_prop,
            note="不動產市值計入淨資產；設定出售年齡後，扣除交易成本與綁定貸款的餘額，其餘入帳。不含房地合一稅，可調高交易成本估算。",
            widths=(170, 150, 150, 110, 110, 170), height=6)
        self.prop_tree.column("value", anchor="e")
        self.prop_tree.column("buy", anchor="e")
        self.sale_tree = self._table_card(
            self.pages["prop"].inner, "出售試算（依最近一次試算結果）",
            ("name", "age", "price", "cost", "payoff", "tax", "net", "gain", "gat", "now"),
            ("名稱", "出售年齡", "預估售價", "交易成本", "償還貸款", "獲利稅", "實拿現金", "獲利（稅前）", "獲利（稅後）", "較目前增值"),
            "獲利 = 售價 − 交易成本 − 購入價；需填寫購入價才會計算。實拿現金 = 售價 − 交易成本 − 償還貸款 − 獲利稅。", 112, 3)
        self.sale_tree.insert("", "end", values=("尚未試算", "", "", "", "", "", "", "", "", ""))
        self.ins_tree = self._list_card(
            self.pages["ins"].inner, "保險", ("name", "premium", "ages", "payacct", "payout", "to"),
            ("名稱", "保費 NT$", "繳費年齡", "保費支付帳戶", "滿期金 NT$（領取年齡）", "滿期金入帳帳戶"),
            self.add_ins, self.edit_ins, self.del_ins,
            note="保費列入每月支出；年繳於保單年度起始月扣款。滿期金在領取年齡入帳到指定帳戶。",
            widths=(160, 150, 130, 140, 210, 140), height=12)
        self.ins_tree.column("premium", anchor="e")
        self._build_pension(self.pages["pen"].inner)
        self._build_results(self.pages["res"].inner)

    def _nav_hover(self, key, on):
        if key == self.current_page:
            return
        row, bar, lab = self.nav_items[key]
        bg = "#2D5282" if on else C["navy2"]
        for wdg in (row, bar, lab):
            wdg.configure(bg=bg)

    def show(self, key):
        self.current_page = key
        for k, (row, bar, lab) in self.nav_items.items():
            active = k == key
            row.configure(bg="#10233D" if active else C["navy2"])
            lab.configure(bg="#10233D" if active else C["navy2"], fg="#FFFFFF" if active else "#DDE6F3")
            bar.configure(bg=C["accent"] if active else C["navy2"])
        if key == "flow":
            self._sync_accts()
            self._refresh_policies()
        if key == "income":
            self._refresh_tax_preview()
        self.pages[key].tkraise()
        self.pages[key].to_top()
        if key == "res":
            self.after(50, self._draw_chart)

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

    def _two_cols(self, parent):
        left = tk.Frame(parent, bg=C["bg"])
        right = tk.Frame(parent, bg=C["bg"])
        for c, f in enumerate((left, right)):
            parent.columnconfigure(c, weight=1, uniform="col")
            f.grid(row=0, column=c, sticky="new", padx=(0, 8) if c == 0 else (8, 0))
            f.columnconfigure(0, weight=1)
        return left, right

    def _acct_field(self, card, key, label, default=True):
        """帳戶下拉選單（欄位值存在 Settings 的同名屬性；空白 = 預設）。"""
        var = tk.StringVar()
        self.acct_vars[key] = var
        combo = ttk.Combobox(card, textvariable=var, state="readonly", width=14, values=self._acct_choices(default))
        self.acct_combos.append((combo, default))
        card.field(label, None, "", widget=combo)

    def _card(self, parent, title, keys=(), hint=None, extra=None):
        cd = Card(parent, title, self.fonts, hint=hint)
        for k in keys:
            self._money_entry(cd, k)
        if extra:
            extra(cd)
        cd.pad()
        cd.grid(sticky="ew", pady=(0, 12), row=parent.grid_size()[1], column=0)
        return cd

    def _page_title(self, parent, title, sub):
        tk.Label(parent, text=title, bg=C["bg"], fg=C["navy"], font=self.fonts["h1"], anchor="w").pack(fill="x")
        tk.Label(parent, text=sub, bg=C["bg"], fg=C["muted"], font=self.fonts["small"], anchor="w").pack(
            fill="x", pady=(0, 12))

    def _build_basic(self, p):
        self._page_title(p, "基本資料", "年齡、現金、退休後生活費帳戶、醫療費用與情境設定")
        cols = tk.Frame(p, bg=C["bg"])
        cols.pack(fill="x")
        left, right = self._two_cols(cols)
        self._card(left, "個人資料", ("current_age", "retire_age", "life_expectancy"))
        self._card(left, "現金與投資稅", ("savings_cash", "savings_rate", "gains_tax_rate"))
        def _bucket_extra(c):
            self.vars["bucket_inflate"] = tk.BooleanVar()
            c.widget(ttk.Checkbutton(c, text="額度視為今日幣值，隨通膨逐年調高", variable=self.vars["bucket_inflate"]),
                     pady=(2, 2))
        self._card(right, "退休後生活費帳戶", ("bucket_amount",),
                   hint="退休後每年年初，把此帳戶補足到設定金額（來源與超出流向可在「資金流向」頁指定）；"
                        "年金與退休金月領先進此帳戶，生活費與貸款由此支出。",
                   extra=_bucket_extra)
        self._card(right, "醫療費用", ("medical_start_age", "medical_monthly", "medical_growth"),
                   hint="從起算年齡起每月加計醫療費用，並以高於一般通膨的幅度逐年成長。填 0 表示不計。")
        self._card(right, "情境設定", ("scenario_delta",),
                   hint="試算時同時跑三種情境：悲觀 = 投資帳戶報酬率下調、樂觀 = 上調相同百分點，基準 = 原設定。")

    def _build_income(self, p):
        self._page_title(p, "收入", "固定薪資、年終獎金，以及兼職、租金、股利等額外收入")
        cols = tk.Frame(p, bg=C["bg"])
        cols.pack(fill="x")
        left, right = self._two_cols(cols)
        self._card(left, "固定薪資與稅款準備金",
                   ("salary_net", "salary_withheld", "income_growth", "income_tax_rate", "bonus_months", "bonus_month"),
                   hint="以「實領月薪」輸入；每月預扣的所得稅視為稅款準備金。",
                   extra=lambda c: self._acct_field(c, "salary_account", "實領薪水 / 獎金存入帳戶"))
        self._card(right, "稅款準備金如何運作", (),
                   hint="每年 5 月結算上一年度所得稅：應納稅額 = 課稅所得 × 有效稅率；課稅所得 = 薪資（實領 + 預扣）+ 年終獎金 + "
                        "應稅的額外收入。已預扣的稅款抵繳，多退少補。\n\n"
                        "• 「預扣所得稅」是公司每月代扣、不在實領薪水內的稅；沒有預扣就填 0，全額於 5 月補繳。\n"
                        "• 若你已把「稅務」列在支出裡，請把預扣與稅率設為 0，避免重複計算。\n"
                        "• 預設兩者皆為 0（不計算所得稅）。")
        tp = Card(right, "稅款預估（第一年，依目前輸入）", self.fonts)
        self.tax_preview = tk.Label(tp, text="", bg=C["card"], fg=C["text"], justify="left", anchor="w",
                                    font=self.fonts["base"], wraplength=440)
        tp.widget(self.tax_preview, sticky="w")
        tp.pad()
        tp.grid(sticky="ew", pady=(0, 12), row=right.grid_size()[1], column=0)
        for k in ("salary_net", "salary_withheld", "income_tax_rate", "bonus_months"):
            self.vars[k].trace_add("write", lambda *a: self._refresh_tax_preview())
        self.extra_tree = self._list_card(
            p, "額外收入", ("name", "amount", "ages", "g", "tax", "acct"),
            ("名稱", "金額 NT$", "期間（年齡）", "每年成長 %", "是否課稅", "存入帳戶"),
            self.add_extra, self.edit_extra, self.del_extra,
            note="薪水以外的收入：兼職、租金、股利、顧問費等；年金額平均分攤到每月，可設定期間與成長率，退休後仍可持續。",
            widths=(180, 190, 160, 120, 100, 150), height=6)
        self.extra_tree.column("amount", anchor="e")

    def _build_expense(self, p):
        self._page_title(p, "支出", "生活支出、其他固定支出與一次性收支（貸款、保險、醫療費用請至各自頁面設定）")
        cols = tk.Frame(p, bg=C["bg"])
        cols.pack(fill="x")
        left, right = self._two_cols(cols)
        self._card(left, "生活支出與通膨", ("monthly_expense", "retire_expense", "inflation"),
                   extra=lambda c: self._acct_field(c, "expense_account", "生活支出 / 醫療費用由哪個帳戶支付"))
        self._card(right, "支出項目說明", (),
                   hint="生活支出以今日幣值輸入，隨通膨逐年上調。\n貸款、保險、醫療費用另於各頁設定；"
                        "子女教育、孝親費、旅遊等有期限的支出請加入「其他固定支出」；買車、出國、遺產等請加入「一次性收支」。")
        self.xexp_tree = self._list_card(
            p, "其他固定支出", ("name", "amount", "ages", "infl", "acct"),
            ("名稱", "金額 NT$（今日幣值）", "期間（年齡）", "隨通膨調整", "支付帳戶"),
            self.add_xexp, self.edit_xexp, self.del_xexp,
            note="子女教育、孝親費、旅遊等：年金額平均分攤到每月，有起訖年齡。",
            widths=(190, 210, 170, 120, 150), height=5)
        self.xexp_tree.column("amount", anchor="e")
        self.oneoff_tree = self._list_card(
            p, "一次性收支", ("name", "kind", "amount", "age", "acct"),
            ("名稱", "類型", "金額 NT$（名目）", "發生年齡", "入帳帳戶"),
            self.add_oneoff, self.edit_oneoff, self.del_oneoff,
            note="買車、出國、子女教育金、遺產入帳等一次性款項；支出走一般現金流，收入入帳到指定帳戶。",
            widths=(200, 100, 200, 130, 180), height=5)
        self.oneoff_tree.column("amount", anchor="e")

    def _build_pension(self, p):
        self._page_title(p, "退休金 / 勞保", "退休金專戶（勞退新制、私校退撫儲金）、雇主另給的退休金，以及勞保老年年金")
        cols = tk.Frame(p, bg=C["bg"])
        cols.pack(fill="x")
        c1 = Card(cols, "退休金專戶（勞退新制 / 私校退撫儲金）", self.fonts,
                  hint="提繳比例請依薪資單設定。一次領會在請領時轉入「退休金帳戶」繼續投資。")
        self.vars["lp_enabled"] = tk.BooleanVar()
        c1.widget(ttk.Checkbutton(c1, text="計入退休金專戶", variable=self.vars["lp_enabled"]), pady=(2, 2))
        for k in ("lp_balance", "lp_return", "lp_monthly_add", "lp_wage", "lp_wage_cap", "lp_employer_pct",
                  "lp_self_pct", "lp_claim_age"):
            self._money_entry(c1, k)
        self.vars["lp_lump_sum"] = tk.StringVar()
        c1.field("領取方式", None, "", widget=ttk.Combobox(c1, textvariable=self.vars["lp_lump_sum"],
                                                         values=["月領", "一次領"], state="readonly", width=14))
        c1.widget(ttk.Button(c1, text="設定「退休金帳戶」投資階段", style="Small.TButton",
                             command=self.edit_lump_stages), pady=(4, 12))
        c2 = Card(cols, "雇主另給的退休金", self.fonts,
                  hint="退休當月一次領，轉入「退休金帳戶」，與專戶一次領的金額合併投資。填 0 表示沒有。")
        self._money_entry(c2, "employer_lump")
        c2.pad()
        c3 = Card(cols, "勞保老年年金", self.fonts,
                  hint="公式：年資 ×（投保薪資 × 0.775% + 3,000）與（投保薪資 × 1.55%）取高者；"
                       "提前/延後每年 ∓4%（最多 5 年）。年資 = 目前年資 + 退休前繼續投保年數。"
                       "投保薪資上限以現行規定為準。")
        self.vars["li_enabled"] = tk.BooleanVar()
        c3.widget(ttk.Checkbutton(c3, text="計入勞保老年年金（預設 65 歲起領）", variable=self.vars["li_enabled"]),
                  pady=(2, 2))
        for k in ("li_avg_wage", "li_years_now", "li_claim_age", "li_manual_monthly"):
            self._money_entry(c3, k)
        self._acct_field(c3, "pension_account", "年金 / 退休金月領存入帳戶")
        c3.pad()
        for c in (0, 1):
            cols.columnconfigure(c, weight=1, uniform="col")
        c1.grid(row=0, column=0, rowspan=2, sticky="nsew", padx=(0, 8), pady=(0, 12))
        c2.grid(row=0, column=1, sticky="new", padx=(8, 0), pady=(0, 12))
        c3.grid(row=1, column=1, sticky="new", padx=(8, 0), pady=(0, 12))

    def _list_card(self, parent, title, cols, heads, add, edit, delete, reorder=None, note="", widths=None,
                   height=8, edit_only=False):
        card = tk.Frame(parent, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
        card.pack(fill="x", pady=(0, 12))
        bar0 = tk.Frame(card, bg=C["card"])
        bar0.pack(fill="x", padx=16, pady=(12, 2))
        tk.Frame(bar0, bg=C["accent"], width=4, height=16).pack(side="left", padx=(0, 8))
        tk.Label(bar0, text=title, bg=C["card"], fg=C["navy"], font=self.fonts["h2"]).pack(side="left")
        if note:
            ttk.Label(card, text=note, style="Muted.TLabel", wraplength=900, justify="left").pack(
                anchor="w", padx=16, pady=(0, 4))
        tree = ttk.Treeview(card, columns=cols, show="headings", height=height, selectmode="browse")
        for i, (c, h) in enumerate(zip(cols, heads)):
            tree.heading(c, text=h)
            tree.column(c, width=(widths[i] if widths else 150), anchor="center")
        tree.tag_configure("odd", background=C["stripe"])
        tree.pack(fill="x", padx=16, pady=6)
        bar = ttk.Frame(card, style="Card.TFrame")
        bar.pack(fill="x", padx=16, pady=(2, 14))
        if edit_only:
            ttk.Button(bar, text="編輯規則", style="Primary.TButton", command=edit).pack(side="left")
        else:
            ttk.Button(bar, text="＋ 新增", style="Primary.TButton", command=add).pack(side="left")
            ttk.Button(bar, text="編輯", command=edit).pack(side="left", padx=6)
            ttk.Button(bar, text="刪除", command=delete).pack(side="left")
        if reorder:
            ttk.Button(bar, text="▲ 上移", command=lambda: reorder(-1)).pack(side="left", padx=(24, 6))
            ttk.Button(bar, text="▼ 下移", command=lambda: reorder(1)).pack(side="left")
        tree.bind("<Double-1>", lambda e: edit())
        return tree

    def _table_card(self, parent, title, cols, heads, note="", width=110, height=4):
        card = tk.Frame(parent, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
        card.pack(fill="x", pady=(0, 12))
        bar0 = tk.Frame(card, bg=C["card"])
        bar0.pack(fill="x", padx=16, pady=(12, 2))
        tk.Frame(bar0, bg=C["accent"], width=4, height=16).pack(side="left", padx=(0, 8))
        tk.Label(bar0, text=title, bg=C["card"], fg=C["navy"], font=self.fonts["h2"]).pack(side="left")
        if note:
            ttk.Label(card, text=note, style="Muted.TLabel", wraplength=900, justify="left").pack(
                anchor="w", padx=16, pady=(0, 4))
        wrap = tk.Frame(card, bg=C["card"])
        wrap.pack(fill="x", padx=16, pady=(4, 14))
        tree = ttk.Treeview(wrap, columns=cols, show="headings", height=height if height > 6 else min(height, 6),
                            selectmode="none")
        xs = ttk.Scrollbar(wrap, orient="horizontal", command=tree.xview)
        tree.configure(xscrollcommand=xs.set)
        for c, h in zip(cols, heads):
            tree.heading(c, text=h)
            tree.column(c, width=width, anchor="e" if c not in ("name", "age") else "center", stretch=False)
        tree.pack(fill="x")
        xs.pack(fill="x")
        tree.tag_configure("odd", background=C["stripe"])
        return tree

    def _build_flow(self, p):
        self._page_title(p, "資金流向", "收入存入哪個帳戶、支出由哪個帳戶支付，以及帳戶的「上限」與「固定額度」規則")
        card = tk.Frame(p, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
        card.pack(fill="x", pady=(0, 12))
        bar0 = tk.Frame(card, bg=C["card"])
        bar0.pack(fill="x", padx=16, pady=(12, 2))
        tk.Frame(bar0, bg=C["accent"], width=4, height=16).pack(side="left", padx=(0, 8))
        tk.Label(bar0, text="資金流向總覽", bg=C["card"], fg=C["navy"], font=self.fonts["h2"]).pack(side="left")
        self.flow_label = tk.Label(card, text="", bg=C["card"], fg=C["text"], justify="left", anchor="w",
                                   font=self.fonts["base"], wraplength=980)
        self.flow_label.pack(fill="x", padx=18, pady=(4, 14))
        self.policy_tree = self._list_card(
            p, "帳戶規則（上限 / 固定額度）", ("acct", "rule", "amt", "over", "src"),
            ("帳戶", "規則", "金額 NT$", "超出部分流向", "不足時補足來源"),
            None, self.edit_policy, None, edit_only=True,
            note="「上限」：帳戶超過上限時，多出的錢每月自動轉到指定帳戶（例如活存超過 100 萬就轉去投資）。"
                 "「固定額度」：每年 1 月把帳戶調整到固定金額，不足由來源補、超出轉出。雙擊或按「編輯」設定。",
            widths=(170, 220, 150, 190, 230), height=7)
        self.policy_tree.column("amt", anchor="e")

    def _build_results(self, p):
        self._page_title(p, "試算結果", "基準情境的關鍵指標、三情境比較與逐年明細")
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
                         justify="left", wraplength=230)
            t.pack(fill="x", padx=14, pady=(10, 0))
            v.pack(fill="x", padx=14)
            s.pack(fill="x", padx=14, pady=(0, 10))
            self.kpis.append((f, t, v, s))
        # 財務指標
        hc = tk.Frame(p, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
        hc.pack(fill="x", pady=(10, 0))
        hb = tk.Frame(hc, bg=C["card"])
        hb.pack(fill="x", padx=16, pady=(10, 0))
        tk.Frame(hb, bg=C["accent"], width=4, height=16).pack(side="left", padx=(0, 8))
        tk.Label(hb, text="財務指標", bg=C["card"], fg=C["navy"], font=self.fonts["h2"]).pack(side="left")
        row = tk.Frame(hc, bg=C["card"])
        row.pack(fill="x", padx=10, pady=(4, 10))
        self.stats = []
        for i in range(5):
            row.columnconfigure(i, weight=1, uniform="st")
            f = tk.Frame(row, bg=C["card"])
            f.grid(row=0, column=i, sticky="nsew", padx=6)
            t = tk.Label(f, text="", bg=C["card"], fg=C["muted"], font=self.fonts["small"], anchor="nw",
                         wraplength=190, justify="left", height=2)
            v = tk.Label(f, text="—", bg=C["card"], fg=C["navy"], font=self.fonts["h2"], anchor="w")
            s = tk.Label(f, text="", bg=C["card"], fg=C["muted"], font=self.fonts["small"], anchor="w",
                         wraplength=190, justify="left")
            t.pack(fill="x")
            v.pack(fill="x")
            s.pack(fill="x")
            self.stats.append((t, v, s))
        self.cf_tree = self._table_card(
            p, "目前每月現金流明細（第一年平均，已把年繳項目平均到每月）", ("item", "amt"), ("項目", "每月平均 NT$"),
            "用來對照你自己的算法：收入 − 支出 − 投資加碼 = 每月淨現金流。", 200, 11)
        self.cf_tree.column("item", width=260, anchor="w")
        self.cf_tree.column("amt", width=180, anchor="e")
        self.cf_tree.tag_configure("head", background="#E8EEF8", foreground=C["navy"])
        self.cf_tree.tag_configure("total", background="#FFF4D6")
        self.alert = tk.Label(p, text="", bg=C["bg"], fg=C["warn"], anchor="w", justify="left",
                              font=self.fonts["small"], wraplength=1000)
        self.alert.pack(fill="x", pady=(6, 0))
        mid = tk.Frame(p, bg=C["bg"])
        mid.pack(fill="x", pady=(6, 8))
        sc = tk.Frame(mid, bg=C["card"], highlightthickness=1, highlightbackground=C["line"], width=360)
        sc.pack(side="right", fill="y", padx=(8, 0))
        sc.pack_propagate(False)
        chart_card = tk.Frame(mid, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
        chart_card.pack(side="left", fill="both", expand=True)
        self.canvas = tk.Canvas(chart_card, height=270, bg=C["card"], highlightthickness=0)
        self.canvas.pack(fill="both", expand=True, padx=6, pady=6)
        self.canvas.bind("<Configure>", lambda e: self._draw_chart())
        self.canvas.bind("<Motion>", self._hover)
        self.canvas.bind("<Leave>", lambda e: self.canvas.delete("hover"))
        tk.Label(sc, text="情境比較", bg=C["card"], fg=C["navy"], font=self.fonts["h2"]).pack(
            anchor="w", padx=14, pady=(10, 4))
        self.sc_tree = ttk.Treeview(sc, columns=("n", "r", "e", "d"), show="headings", height=3,
                                    selectmode="none")
        for c, h, w_ in (("n", "情境", 50), ("r", "退休時淨資產", 98), ("e", "壽命時淨資產", 98), ("d", "耗盡", 56)):
            self.sc_tree.heading(c, text=h)
            self.sc_tree.column(c, width=w_, anchor="e" if c in "re" else "center", stretch=False)
        self.sc_tree.pack(fill="x", padx=12)
        self.sc_note = tk.Label(sc, text="", bg=C["card"], fg=C["muted"], font=self.fonts["small"],
                                justify="left", anchor="w", wraplength=330)
        self.sc_note.pack(fill="x", padx=14, pady=(6, 4))
        self.show_prop = tk.BooleanVar(value=True)
        ttk.Checkbutton(sc, text="圖表含不動產市值", variable=self.show_prop,
                        command=self._draw_chart).pack(anchor="w", padx=14, pady=(2, 0))
        bar = tk.Frame(p, bg=C["bg"])
        bar.pack(fill="x", pady=(0, 4))
        ttk.Label(bar, text="逐年表情境：").pack(side="left")
        self.table_scn = tk.StringVar(value="基準")
        cb = ttk.Combobox(bar, textvariable=self.table_scn, values=["悲觀", "基準", "樂觀"], state="readonly",
                          width=6)
        cb.pack(side="left")
        cb.bind("<<ComboboxSelected>>", lambda e: self._fill_table())
        tbl = tk.Frame(p, bg=C["card"], highlightthickness=1, highlightbackground=C["line"])
        tbl.pack(fill="x")
        self.res_tree = ttk.Treeview(tbl, show="headings", height=12)
        ys = ttk.Scrollbar(tbl, orient="vertical", command=self.res_tree.yview)
        xs = ttk.Scrollbar(tbl, orient="horizontal", command=self.res_tree.xview)
        self.res_tree.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        ys.pack(side="right", fill="y")
        xs.pack(side="bottom", fill="x")
        self.res_tree.pack(fill="x")
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
        for key, v in self.acct_vars.items():
            v.set(self._acct_label(getattr(s, key), self._acct_choices(True), True))
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
        for key, v in self.acct_vars.items():
            setattr(s, key, self._acct_store(v.get()))
        return s

    def _refresh_lists(self):
        for combo, default in self.acct_combos:
            combo["values"] = self._acct_choices(default)
        self._refresh_policies()
        self._refresh_tax_preview()
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
            self.loan_tree.insert("", "end", values=(l.name, mode, amt, l.start, end, l.pay_account or "預設"),
                                  tags=("odd" if i % 2 else "even",))

        self.prop_tree.delete(*self.prop_tree.get_children())
        for i, x in enumerate(self.s.properties):
            sell = f"{x.sell_age:g} 歲" if x.sell_age > 0 else "不出售"
            self.prop_tree.insert("", "end", tags=("odd" if i % 2 else "even",),
                                  values=(x.name, money(x.value), money(x.purchase_price) if x.purchase_price else "—",
                                          f"{x.appreciation:g}", sell, x.loan_name or "—"))
        self.ins_tree.delete(*self.ins_tree.get_children())
        for i, x in enumerate(self.s.insurances):
            pay = f"{money(x.premium)} / {'年' if x.freq == 'year' else '月'}"
            out = f"{money(x.payout)}（{(x.payout_age or x.end_age):g} 歲）" if x.payout > 0 else "—"
            self.ins_tree.insert("", "end", tags=("odd" if i % 2 else "even",),
                                 values=(x.name, pay, f"{x.start_age:g}–{x.end_age:g} 歲", x.pay_account or "預設", out,
                                         x.payout_to or "活存"))
        self.extra_tree.delete(*self.extra_tree.get_children())
        for i, x in enumerate(self.s.extra_incomes):
            amt = f"{money(x.amount)} / {'年' if x.freq == 'year' else '月'}"
            self.extra_tree.insert("", "end", tags=("odd" if i % 2 else "even",),
                                   values=(x.name, amt, f"{x.start_age:g}–{x.end_age:g} 歲", f"{x.growth:g}",
                                           "是" if x.taxable else "否", x.account or "預設"))

        self.xexp_tree.delete(*self.xexp_tree.get_children())
        for i, x in enumerate(self.s.extra_expenses):
            amt = f"{money(x.amount)} / {'年' if x.freq == 'year' else '月'}"
            self.xexp_tree.insert("", "end", tags=("odd" if i % 2 else "even",),
                                  values=(x.name, amt, f"{x.start_age:g}–{x.end_age:g} 歲",
                                          "是" if x.inflation_adjust else "否", x.pay_account or "預設"))
        self.oneoff_tree.delete(*self.oneoff_tree.get_children())
        for i, x in enumerate(self.s.one_offs):
            self.oneoff_tree.insert("", "end", tags=("odd" if i % 2 else "even",),
                                    values=(x.name, "收入" if x.kind == "in" else "支出", money(x.amount),
                                            f"{x.age:g} 歲", (x.account or "活存") if x.kind == "in" else "—"))

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
        ch = self._acct_choices(True)
        d = FormDialog(self, "房貸/貸款", [
            ("name", "名稱", "text", l.name),
            ("mode", "計算方式", "choice", names[1] if l.mode == "amort" else names[0], names),
            ("monthly_payment", "每月扣款 NT$（固定月扣款用）", "num", l.monthly_payment),
            ("principal", "原貸款金額 NT$（攤還用）", "num", l.principal),
            ("annual_rate", "年利率 %（攤還用）", "num", l.annual_rate),
            ("start", "起始年月 YYYY-MM", "text", l.start),
            ("end", "結束年月 YYYY-MM（含）", "text", l.end),
            ("years", "或貸款年限（結束年月留空時，攤還用）", "num", l.years),
            ("pay_account", "還款由哪個帳戶支付", "choice", self._acct_label(l.pay_account, ch, True), ch)])
        if not d.result:
            return None
        r = d.result
        r["mode"] = "amort" if r["mode"] == names[1] else "fixed"
        r["pay_account"] = self._acct_store(r["pay_account"])
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

    NONE = "（無）"
    DEFAULT = "（預設）"

    def add_prop(self):
        self._crud(self.prop_tree, self.s.properties, self._prop_dialog, Property)[0]()

    def edit_prop(self):
        self._crud(self.prop_tree, self.s.properties, self._prop_dialog, Property)[1]()

    def del_prop(self):
        self._crud(self.prop_tree, self.s.properties, self._prop_dialog, Property)[2]()

    def _new_ins(self):
        return Insurance(start_age=self.s.current_age, end_age=self.s.current_age + 20)

    def add_ins(self):
        self._crud(self.ins_tree, self.s.insurances, self._ins_dialog, self._new_ins)[0]()

    def edit_ins(self):
        self._crud(self.ins_tree, self.s.insurances, self._ins_dialog, self._new_ins)[1]()

    def del_ins(self):
        self._crud(self.ins_tree, self.s.insurances, self._ins_dialog, self._new_ins)[2]()

    def _new_xexp(self):
        return ExtraExpense(start_age=self.s.current_age, end_age=self.s.current_age + 10)

    def add_xexp(self):
        self._crud(self.xexp_tree, self.s.extra_expenses, self._xexp_dialog, self._new_xexp)[0]()

    def edit_xexp(self):
        self._crud(self.xexp_tree, self.s.extra_expenses, self._xexp_dialog, self._new_xexp)[1]()

    def del_xexp(self):
        self._crud(self.xexp_tree, self.s.extra_expenses, self._xexp_dialog, self._new_xexp)[2]()

    def _new_oneoff(self):
        return OneOff(age=self.s.current_age + 5)

    def add_oneoff(self):
        self._crud(self.oneoff_tree, self.s.one_offs, self._oneoff_dialog, self._new_oneoff)[0]()

    def edit_oneoff(self):
        self._crud(self.oneoff_tree, self.s.one_offs, self._oneoff_dialog, self._new_oneoff)[1]()

    def del_oneoff(self):
        self._crud(self.oneoff_tree, self.s.one_offs, self._oneoff_dialog, self._new_oneoff)[2]()

    def _new_extra(self):
        return ExtraIncome(start_age=self.s.current_age, end_age=self.s.retire_age)

    def add_extra(self):
        self._crud(self.extra_tree, self.s.extra_incomes, self._extra_dialog, self._new_extra)[0]()

    def edit_extra(self):
        self._crud(self.extra_tree, self.s.extra_incomes, self._extra_dialog, self._new_extra)[1]()

    def del_extra(self):
        self._crud(self.extra_tree, self.s.extra_incomes, self._extra_dialog, self._new_extra)[2]()

    def _acct_choices(self, default=False):
        """可選帳戶：活存、生活費帳戶、各投資帳戶、退休金帳戶（存在時）。default=True 時最前面加「（預設）」。"""
        extra = ["退休金帳戶"] if (self.s.lp_enabled and self.s.lp_lump_sum) or self.s.employer_lump > 0 else []
        return ([self.DEFAULT] if default else []) + [CASH, BUCKET] + [a.name for a in self.s.accounts] + extra

    def _acct_label(self, stored, choices, default=False):
        if stored and stored in choices:
            return stored
        return self.DEFAULT if default else CASH

    def _acct_store(self, label):
        return "" if label == self.DEFAULT else label

    def _crud(self, tree, items, dialog, new):
        """回傳 (add, edit, delete)。"""
        def add():
            x = dialog(new())
            if x:
                items.append(x)
                self._refresh_lists()

        def edit():
            i = self._sel(tree)
            if i is not None:
                x = dialog(items[i])
                if x:
                    items[i] = x
                    self._refresh_lists()

        def delete():
            i = self._sel(tree)
            if i is not None:
                del items[i]
                self._refresh_lists()
        return add, edit, delete

    def _xexp_dialog(self, x: ExtraExpense):
        ch = self._acct_choices(True)
        d = FormDialog(self, "其他固定支出", [
            ("name", "名稱", "text", x.name), ("amount", "金額 NT$（今日幣值）", "num", x.amount),
            ("freq", "金額單位", "choice", "每年" if x.freq == "year" else "每月", ["每月", "每年"]),
            ("start_age", "起始年齡", "num", x.start_age), ("end_age", "結束年齡（到該歲生日前為止）", "num", x.end_age),
            ("inflation_adjust", "隨通膨調整", "choice", "是" if x.inflation_adjust else "否", ["是", "否"]),
            ("pay_account", "由哪個帳戶支付", "choice", self._acct_label(x.pay_account, ch, True), ch)])
        if not d.result:
            return None
        r = d.result
        r["freq"] = "year" if r["freq"] == "每年" else "month"
        r["inflation_adjust"] = r["inflation_adjust"] == "是"
        r["pay_account"] = self._acct_store(r["pay_account"])
        return ExtraExpense(**r)

    def _oneoff_dialog(self, x: OneOff):
        choices = self._acct_choices()
        d = FormDialog(self, "一次性收支", [
            ("name", "名稱", "text", x.name),
            ("kind", "類型", "choice", "收入" if x.kind == "in" else "支出", ["支出", "收入"]),
            ("amount", "金額 NT$（名目）", "num", x.amount), ("age", "發生年齡", "num", x.age),
            ("account", "收入入帳帳戶（支出走「支出帳戶」）", "choice", self._acct_label(x.account, choices), choices)])
        if not d.result:
            return None
        r = d.result
        r["kind"] = "in" if r["kind"] == "收入" else "out"
        return OneOff(**r)

    def _extra_dialog(self, x: ExtraIncome):
        ch = self._acct_choices(True)
        d = FormDialog(self, "額外收入", [
            ("name", "名稱", "text", x.name), ("amount", "金額 NT$", "num", x.amount),
            ("freq", "金額單位", "choice", "每年" if x.freq == "year" else "每月", ["每月", "每年"]),
            ("start_age", "起始年齡", "num", x.start_age), ("end_age", "結束年齡（到該歲生日前為止）", "num", x.end_age),
            ("growth", "每年成長 %", "num", x.growth),
            ("taxable", "是否計入所得稅", "choice", "是" if x.taxable else "否", ["是", "否"]),
            ("account", "收入存入哪個帳戶", "choice", self._acct_label(x.account, ch, True), ch)])
        if not d.result:
            return None
        r = d.result
        r["freq"] = "year" if r["freq"] == "每年" else "month"
        r["taxable"] = r["taxable"] == "是"
        r["account"] = self._acct_store(r["account"])
        return ExtraIncome(**r)

    def _ins_dialog(self, x: Insurance):
        choices = self._acct_choices()
        ch = self._acct_choices(True)
        d = FormDialog(self, "保險", [
            ("name", "名稱", "text", x.name), ("premium", "保費 NT$", "num", x.premium),
            ("freq", "繳費方式", "choice", "每年" if x.freq == "year" else "每月", ["每月", "每年"]),
            ("start_age", "繳費起始年齡", "num", x.start_age), ("end_age", "繳費結束年齡（到該歲生日前為止）", "num", x.end_age),
            ("inflation_adjust", "保費隨通膨調整", "choice", "是" if x.inflation_adjust else "否", ["否", "是"]),
            ("pay_account", "保費由哪個帳戶支付", "choice", self._acct_label(x.pay_account, ch, True), ch),
            ("payout", "滿期金 / 理賠金 NT$（0 = 無）", "num", x.payout),
            ("payout_age", "領取年齡（0 = 繳費結束時）", "num", x.payout_age),
            ("payout_to", "滿期金入帳帳戶", "choice", self._acct_label(x.payout_to, choices), choices)])
        if not d.result:
            return None
        r = d.result
        r["freq"] = "year" if r["freq"] == "每年" else "month"
        r["inflation_adjust"] = r["inflation_adjust"] == "是"
        r["pay_account"] = self._acct_store(r["pay_account"])
        return Insurance(**r)

    def _prop_dialog(self, x: Property):
        accts = self._acct_choices()
        loans = [self.NONE] + [l.name for l in self.s.loans]
        d = FormDialog(self, "不動產", [
            ("name", "名稱", "text", x.name), ("value", "目前市值 NT$", "num", x.value),
            ("purchase_price", "購入價 NT$（0 = 不計算獲利）", "num", x.purchase_price),
            ("appreciation", "年增值率 %", "num", x.appreciation),
            ("sell_age", "出售年齡（0 = 不出售）", "num", x.sell_age),
            ("sell_cost", "交易成本 %（仲介、稅費）", "num", x.sell_cost),
            ("sell_tax_rate", "出售獲利稅率 %（如房地合一稅）", "num", x.sell_tax_rate),
            ("loan_name", "出售時一併還清的貸款", "choice", x.loan_name if x.loan_name in loans else self.NONE, loans),
            ("proceeds_to", "售屋款入帳帳戶", "choice", self._acct_label(x.proceeds_to, accts), accts)])
        if not d.result:
            return None
        r = d.result
        r["loan_name"] = "" if r["loan_name"] == self.NONE else r["loan_name"]
        return Property(**r)

    # ---------- 帳戶規則 / 資金流向 ----------
    MODE_LABELS = {"none": "無規則", "cap": "上限（超過轉出）", "fixed": "固定額度（每年 1 月）"}

    def _refresh_tax_preview(self):
        if not hasattr(self, "tax_preview"):
            return

        def num(k):
            try:
                return float(self.vars[k].get().replace(",", "") or 0)
            except ValueError:
                return None
        net, wh, rate, bm = (num(k) for k in ("salary_net", "salary_withheld", "income_tax_rate", "bonus_months"))
        if None in (net, wh, rate, bm):
            self.tax_preview.config(text="請先輸入有效數字")
            return
        s = self.s
        extra_tax = sum(x.amount * (1 if x.freq == "year" else 12) for x in s.extra_incomes
                        if x.taxable and x.start_age <= s.current_age < x.end_age)
        income = (net + wh) * 12 + net * bm + extra_tax
        tax = income * rate / 100
        diff = wh * 12 - tax
        word = "退稅" if diff >= 0 else "補稅"
        self.tax_preview.config(text=(
            f"課稅所得約 {money(income)}（薪資 {money((net + wh) * 12)}"
            f"{'、獎金 ' + money(net * bm) if bm else ''}{'、應稅額外收入 ' + money(extra_tax) if extra_tax else ''}）\n"
            f"應納稅額 = {money(income)} × {rate:g}% = {money(tax)}；已預扣 {money(wh * 12)}\n"
            f"每年{word} {money(abs(diff))}（約每月 {money(abs(diff) / 12)}）"))

    def _sync_accts(self):
        for key, v in self.acct_vars.items():
            setattr(self.s, key, self._acct_store(v.get()))

    def _policy_of(self, name):
        return next((p_ for p_ in self.s.policies if p_.account == name), None)

    def _refresh_policies(self):
        if not hasattr(self, "policy_tree"):
            return
        tree = self.policy_tree
        tree.delete(*tree.get_children())
        for i, name in enumerate(self._acct_choices()):
            p_ = self._policy_of(name)
            if name == BUCKET:
                rule, amt = "固定額度（退休後每年年初）", money(self.s.bucket_amount) + ("（今日幣值）" if self.s.bucket_inflate else "")
                over = (p_.overflow_to if p_ and p_.overflow_to else "不轉出")
                src = (p_.refill_from if p_ and p_.refill_from else "依投資帳戶清單順序")
            elif p_ and p_.mode != "none":
                rule, amt = self.MODE_LABELS[p_.mode], money(p_.limit)
                over = p_.overflow_to or "不轉出"
                src = (p_.refill_from or "依投資帳戶清單順序") if p_.mode == "fixed" else "—"
            else:
                rule, amt, over, src = "無規則", "—", "—", "—"
            tree.insert("", "end", values=(name, rule, amt, over, src), tags=("odd" if i % 2 else "even",))
        self._refresh_flow_text()

    def _refresh_flow_text(self):
        if not hasattr(self, "flow_label"):
            return
        s = self.s
        dflt = "預設（退休前＝活存，退休後＝生活費帳戶）"
        lines = ["【收入存入】",
                 f"  • 實領薪水 / 年終獎金 → {s.salary_account or dflt}"]
        lines += [f"  • 額外收入「{x.name}」 → {x.account or dflt}" for x in s.extra_incomes]
        lines += [f"  • 勞保年金 / 退休金月領 → {s.pension_account or dflt}", "", "【支出由哪個帳戶支付】",
                  f"  • 生活支出、醫療費用、一次性支出 ← {s.expense_account or dflt}"]
        lines += [f"  • 貸款「{x.name}」 ← {x.pay_account or dflt}" for x in s.loans]
        lines += [f"  • 保險「{x.name}」 ← {x.pay_account or dflt}" for x in s.insurances]
        lines += [f"  • 其他固定支出「{x.name}」 ← {x.pay_account or dflt}" for x in s.extra_expenses]
        lines += ["  • 每月投資加碼 ← 預設現金流（退休前＝活存）", "",
                  "【不足時怎麼辦】指定帳戶餘額不夠時，缺口併入「預設帳戶」；預設帳戶也不夠時，依序動用："
                  "投資帳戶（依清單順序）→ 退休金帳戶 → 活存；全部耗盡才算資產耗盡。"]
        rules = []
        for p_ in s.policies:
            if p_.account == BUCKET:
                continue
            if p_.mode == "cap" and p_.overflow_to:
                rules.append(f"  • 「{p_.account}」超過 {money(p_.limit)} 的部分 → 轉入「{p_.overflow_to}」")
            elif p_.mode == "fixed":
                rules.append(f"  • 「{p_.account}」每年 1 月調整為 {money(p_.limit)}"
                             f"（不足由「{p_.refill_from or '投資帳戶依序'}」補，超出轉入「{p_.overflow_to or '不轉出'}」）")
        bp = self._policy_of(BUCKET)
        rules.append(f"  • 「生活費帳戶」退休後每年年初補足到 {money(s.bucket_amount)}"
                     f"{'（今日幣值，隨通膨調整）' if s.bucket_inflate else ''}"
                     f"，來源：{(bp.refill_from if bp and bp.refill_from else '投資帳戶依序')}"
                     f"，超出：{(bp.overflow_to if bp and bp.overflow_to else '不轉出')}")
        lines += ["", "【帳戶規則】"] + rules
        self.flow_label.config(text="\n".join(lines))

    def edit_policy(self):
        sel = self.policy_tree.selection()
        if not sel:
            return
        name = self.policy_tree.item(sel[0], "values")[0]
        p_ = self._policy_of(name) or Policy(account=name)
        others = [c for c in self._acct_choices() if c != name]
        none_over, none_src = "（不轉出）", "（依投資帳戶清單順序）"
        over_ch, src_ch = [none_over] + others, [none_src] + others
        over = p_.overflow_to if p_.overflow_to in others else none_over
        src = p_.refill_from if p_.refill_from in others else none_src
        if name == BUCKET:
            fields = [("limit", "每年年初補足金額 NT$", "num", self.s.bucket_amount),
                      ("refill_from", "不足時由哪個帳戶補足", "choice", src, src_ch),
                      ("overflow_to", "超出部分流向", "choice", over, over_ch)]
        else:
            labels = list(self.MODE_LABELS.values())
            fields = [("mode", "規則", "choice", self.MODE_LABELS[p_.mode], labels),
                      ("limit", "上限 / 固定額度 NT$", "num", p_.limit),
                      ("overflow_to", "超出部分流向（上限 / 固定額度共用）", "choice", over, over_ch),
                      ("refill_from", "固定額度不足時的補足來源", "choice", src, src_ch)]
        d = FormDialog(self, f"帳戶規則：{name}", fields)
        if not d.result:
            return
        r = d.result
        new = Policy(account=name, mode="fixed" if name == BUCKET else "none", limit=0.0)
        if name != BUCKET:
            new.mode = next(k for k, v in self.MODE_LABELS.items() if v == r["mode"])
            new.limit = r["limit"]
        else:
            self.s.bucket_amount = r["limit"]
            self.vars["bucket_amount"].set(f"{r['limit']:,.0f}")
        new.overflow_to = "" if r["overflow_to"] == none_over else r["overflow_to"]
        new.refill_from = "" if r["refill_from"] == none_src else r["refill_from"]
        self.s.policies = [x for x in self.s.policies if x.account != name]
        if name == BUCKET or new.mode != "none":
            self.s.policies.append(new)
        self._refresh_policies()

    def _fill_sales(self, r: Result):
        tree = self.sale_tree
        tree.delete(*tree.get_children())
        for i, x in enumerate(r.property_sales):
            g = x["gain"]
            tree.insert("", "end", tags=("odd" if i % 2 else "even",), values=(
                x["name"], f"{x['age']:g} 歲", money(x["price"]), money(x["cost"]), money(x["payoff"]),
                money(x["tax"]), money(x["net_cash"]), money(g) if g is not None else "（未填購入價）",
                money(x["gain_after_tax"]) if g is not None else "—", money(x["gain_vs_now"])))
        if not r.property_sales:
            tree.insert("", "end", values=("無出售資料", "", "", "", "", "", "", "", "", ""))

    # ---------- 計算與顯示 ----------
    def calculate(self):
        try:
            self._from_form()
            self.results = simulate_scenarios(self.s)
        except ValueError as e:
            messagebox.showerror("無法試算", str(e))
            return
        self.result = self.results["基準"]
        self._save_auto()
        self.show("res")
        self._render()
        self.status.set(f"試算完成 · {dt.datetime.now():%H:%M:%S} · 設定已自動儲存")

    def _on_basis(self):
        self._draw_chart()

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
        ret_row = next((x for x in r.rows if abs(x.age - s.retire_age) < 0.01), None)
        prop_ret = f"　不動產 {short_money(ret_row.property_value)}" if ret_row and ret_row.property_value else ""
        self._set_kpi(0, f"{s.retire_age:g} 歲退休時淨資產（基準）", f"NT$ {short_money(r.retire_net_worth)}",
                      f"今日購買力 NT$ {short_money(r.retire_real_net_worth)}{prop_ret}")
        self._set_kpi(1, f"{s.life_expectancy:g} 歲時淨資產（基準）", f"NT$ {short_money(end.net_worth)}",
                      f"今日購買力 NT$ {short_money(end.real_net_worth)}\n不含不動產 NT$ {short_money(end.liquid_net_worth)}",
                      C["bad"] if end.net_worth < 0 else None)
        if r.depleted_age:
            self._set_kpi(2, "資產狀態（基準）", f"約 {r.depleted_age:.1f} 歲耗盡", "之後生活費出現缺口，需調整計畫", C["bad"])
        else:
            self._set_kpi(2, "資產狀態（基準）", f"可支撐至 {s.life_expectancy:g} 歲", "全程現金流與流動資產皆為正", C["ok"])
        monthly = r.li_monthly + (0 if s.lp_lump_sum else r.lp_monthly)
        parts = [f"勞保年金 {money(r.li_monthly)}"]
        if s.lp_enabled:
            parts.append(f"退休金一次領 {money(r.lp_at_claim)}（轉入退休金帳戶）" if s.lp_lump_sum
                         else f"退休金月領 {money(r.lp_monthly)}")
        if s.employer_lump > 0:
            parts.append(f"雇主退休金 {money(s.employer_lump)}")
        self._set_kpi(3, "退休後固定月收入", f"NT$ {money(monthly)}", "\n".join(parts))
        infl = 1 + s.inflation / 100
        yrs = max(s.retire_age - s.current_age, 0)
        liq_ret = ret_row.liquid_net_worth if ret_row else r.retire_net_worth
        real_liq = liq_ret / infl ** yrs
        sust = real_liq * 0.04 / 12
        need = s.retire_expense
        need_nom = need * infl ** yrs
        cov = monthly / need_nom if need_nom > 0 else 0
        emerg = s.savings_cash / s.monthly_expense if s.monthly_expense > 0 else 0
        tiles = [
            ("退休時流動資產（今日購買力）", short_money(real_liq), "不含不動產，已扣貸款", None),
            ("4% 法則可持續月提領（今日幣值）", money(sust), f"退休後每月支出需求 {money(need)}",
             C["ok"] if sust >= need else C["warn"]),
            ("固定月收入覆蓋率", f"{cov:.0%}", "勞保年金 + 退休金月領 ÷ 退休後支出",
             C["ok"] if cov >= 0.6 else C["warn"]),
            ("緊急預備金", f"{emerg:.1f} 個月", "活存現金 ÷ 目前每月生活支出",
             C["ok"] if emerg >= 6 else C["warn"]),
            ("目前每月現金流", money(r.monthly_surplus_now), "實領薪水 + 額外收入 − 各項支出 − 投資",
             C["bad"] if r.monthly_surplus_now < 0 else C["ok"]),
        ]
        for (t_, v_, s_), (tt, vv, ss, col) in zip(self.stats, tiles):
            t_.config(text=tt)
            v_.config(text=vv, fg=col or C["navy"])
            s_.config(text=ss)
        self.alert.config(text="    ".join(f"⚠ {w}" for w in r.warnings))

        self.sc_tree.delete(*self.sc_tree.get_children())
        for name in ("悲觀", "基準", "樂觀"):
            x = self.results[name]
            self.sc_tree.insert("", "end", values=(
                name, short_money(x.retire_net_worth), short_money(x.rows[-1].net_worth),
                f"{x.depleted_age:.0f} 歲" if x.depleted_age else "無"))
        d = s.scenario_delta
        self.sc_note.config(text=f"悲觀 / 樂觀：投資帳戶（含退休金帳戶）報酬率 ∓ {d:g} 個百分點；淨資產含不動產。")
        self._fill_table()
        self._fill_sales(r)
        self._fill_cashflow(r)
        self._draw_chart()

    def _fill_cashflow(self, r: Result):
        cf = r.cashflow
        tree = self.cf_tree
        tree.delete(*tree.get_children())
        inc = cf["salary"] + cf["extra"] + cf["pension"] + cf["tax"] + cf["oneoff"]
        out = (cf["living"] + cf["xexp"] + cf["insurance"] + cf["loan"] + cf["medical"] + cf["invest"])
        rows = [("收入", None, "head"), ("　實領薪水", cf["salary"], ""), ("　額外收入", cf["extra"], ""),
                ("　年金 / 退休金月領", cf["pension"], ""), ("　所得稅（退稅＋ / 補稅－，已平均到每月）", cf["tax"], ""),
                ("　一次性收支淨額", cf["oneoff"], ""), ("　收入合計", inc, "head"),
                ("支出與投資", None, "head"), ("　生活支出", cf["living"], ""),
                ("　其他固定支出（旅遊、教育、稅務…）", cf["xexp"], ""), ("　保險保費", cf["insurance"], ""),
                ("　貸款還款", cf["loan"], ""), ("　醫療費用", cf["medical"], ""), ("　每月投資加碼", cf["invest"], ""),
                ("　支出與投資合計", out, "head"), ("每月淨現金流", inc - out, "total")]
        tree.configure(height=len(rows))
        for name, v, tag in rows:
            tree.insert("", "end", values=(name, "" if v is None else money(v)), tags=(tag,) if tag else ())

    def _fill_table(self):
        res = getattr(self, "results", None)
        if not res:
            return
        r = res[self.table_scn.get()]
        s = self.s
        names = r.account_names
        cols = ["age", "income", "extra", "pension", "tax", "expense", "xexp", "oneoff", "med", "ins", "loan",
                "invest"] + \
               [f"a{i}" for i in range(len(names))] + ["free", "bucket", "lp", "prop", "debt", "liq", "nw", "real"]
        heads = ["年齡", "實領薪水", "額外收入", "年金/退休金月領", "稅款結算（＋退稅／−補稅）", "生活支出", "其他固定支出", "一次性收支",
                 "醫療費用", "保險保費", "貸款支出", "新增投資"] + names + ["活存/現金", "生活費帳戶", "退休金專戶", "不動產", "貸款餘額",
                                                  "淨資產(不含不動產)", "淨資產", "淨資產(今日購買力)"]
        self.res_tree.configure(columns=cols)
        for c, h in zip(cols, heads):
            self.res_tree.heading(c, text=h)
            self.res_tree.column(c, width=118 if c != "age" else 64, anchor="e", stretch=False)
        self.res_tree.column("age", anchor="center")
        self.res_tree.delete(*self.res_tree.get_children())
        for i, x in enumerate(r.rows):
            tags = ["odd" if i % 2 else "even"]
            if abs(x.age - s.retire_age) < 0.01:
                tags.append("retire")
            self.res_tree.insert("", "end", tags=tags, values=[
                f"{x.age:g}", money(x.income), money(x.extra_income), money(x.pension_income), money(x.tax_settle),
                money(x.expense), money(x.extra_expense), money(x.one_off), money(x.medical), money(x.insurance),
                money(x.loan_paid), money(x.invested)] +
                [money(b) for b in x.account_balances] +
                [money(x.free_cash), money(x.bucket), money(x.lp_balance), money(x.property_value),
                 money(x.loan_balance), money(x.liquid_net_worth), money(x.net_worth), money(x.real_net_worth)])

    # ---------- 圖表 ----------
    SCN_COLORS = {"悲觀": "#DC2626", "基準": "#2563EB", "樂觀": "#0F9D8A"}

    def _series(self, res: Result):
        """依「含不動產 / 今日購買力」選項取得 (年齡, 數值)。"""
        infl = 1 + self.s.inflation / 100
        out = []
        for x in res.rows:
            v = x.net_worth if self.show_prop.get() else x.liquid_net_worth
            if self.show_real.get():
                v = v / infl ** (x.age - self.s.current_age)
            out.append(v)
        return out

    def _draw_chart(self):
        c = self.canvas
        c.delete("all")
        self._chart = None
        res = getattr(self, "results", None)
        w, h = c.winfo_width(), c.winfo_height()
        if not res or w < 50:
            c.create_text(w / 2 if w > 50 else 200, h / 2, text="按「開始試算」後在此顯示淨資產走勢",
                          fill=C["muted"], font=self.fonts["base"])
            return
        L, R, T, B = 78, 24, 34, 34
        rows = res["基準"].rows
        ages = [x.age for x in rows]
        series = {k: self._series(v) for k, v in res.items()}
        allv = [v for vals in series.values() for v in vals] + [0]
        ticks = nice_ticks(min(allv), max(allv), 4)
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
        ra = self.s.retire_age
        if x0 <= ra <= x1:
            c.create_line(px(ra), T - 6, px(ra), h - B, fill="#D97706", dash=(4, 3))
            c.create_text(px(ra) + 5, T - 8, text=f"退休 {ra:g}", anchor="w", fill="#D97706", font=self.fonts["small"])
        base_pts = [co for a_, v in zip(ages, series["基準"]) for co in (px(a_), py(v))]
        if len(base_pts) >= 4:
            c.create_polygon(*([px(ages[0]), py(0)] + base_pts + [px(ages[-1]), py(0)]), fill="#E3ECFF", outline="")
        for name in ("悲觀", "樂觀", "基準"):
            pts = [co for a_, v in zip(ages, series[name]) for co in (px(a_), py(v))]
            if len(pts) >= 4:
                c.create_line(*pts, fill=self.SCN_COLORS[name], width=3 if name == "基準" else 2,
                              dash=None if name == "基準" else (5, 3))
        lx = L
        for name in ("悲觀", "基準", "樂觀"):
            col = self.SCN_COLORS[name]
            c.create_line(lx, 12, lx + 22, 12, fill=col, width=3 if name == "基準" else 2,
                          dash=None if name == "基準" else (5, 3))
            c.create_text(lx + 28, 12, text=name, anchor="w", fill=C["text"], font=self.fonts["small"])
            lx += 78
        basis = ("今日購買力" if self.show_real.get() else "名目金額") + ("・含不動產" if self.show_prop.get() else "・不含不動產")
        c.create_text(lx + 10, 12, text=basis, anchor="w", fill=C["muted"], font=self.fonts["small"])
        self._chart = {"px": px, "py": py, "ages": ages, "rows": rows, "series": series, "L": L, "R": R,
                       "T": T, "B": B, "w": w, "h": h}

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
        for name in ("悲觀", "基準", "樂觀"):
            y = g["py"](g["series"][name][i])
            c.create_oval(x - 4, y - 4, x + 4, y + 4, fill="#FFFFFF", outline=self.SCN_COLORS[name], width=2,
                          tags="hover")
        lines = [f"{row.age:g} 歲"] + [f"{n}  {money(g['series'][n][i])}" for n in ("樂觀", "基準", "悲觀")] + \
                [f"（基準）不動產  {money(row.property_value)}", f"（基準）貸款餘額  {money(row.loan_balance)}"]
        bw, bh = 214, 18 * len(lines) + 12
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
        if not self.results:
            messagebox.showinfo("提示", "請先按「開始試算」")
            return
        p = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not p:
            return
        scn = self.table_scn.get()
        r = self.results[scn]
        with open(p, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["年齡", "實領薪水", "額外收入", "年金/退休金月領", "稅款結算", "生活支出", "其他固定支出",
                        "一次性收支", "醫療費用", "保險保費", "貸款支出", "新增投資"] + r.account_names +
                       ["活存/現金", "生活費帳戶", "退休金專戶", "不動產", "貸款餘額", "淨資產(不含不動產)", "淨資產",
                        "淨資產(今日購買力)"])
            for x in r.rows:
                w.writerow([x.age, round(x.income), round(x.extra_income), round(x.pension_income),
                            round(x.tax_settle), round(x.expense), round(x.extra_expense), round(x.one_off),
                            round(x.medical), round(x.insurance), round(x.loan_paid), round(x.invested)] +
                           [round(b) for b in x.account_balances] +
                           [round(x.free_cash), round(x.bucket), round(x.lp_balance), round(x.property_value),
                            round(x.loan_balance), round(x.liquid_net_worth), round(x.net_worth),
                            round(x.real_net_worth)])
        self.status.set(f"已匯出 CSV（{scn}情境）：{p}")


    def export_report(self):
        if not self.results:
            messagebox.showinfo("提示", "請先按「開始試算」")
            return
        p = filedialog.asksaveasfilename(defaultextension=".html", filetypes=[("HTML 報告", "*.html")],
                                         initialfile="退休收益預測報告.html")
        if not p:
            return
        with open(p, "w", encoding="utf-8") as f:
            f.write(build_report(self.s, self.results))
        self.status.set(f"報告已產生：{p}（瀏覽器中可列印或另存 PDF）")
        try:
            webbrowser.open("file://" + os.path.abspath(p).replace("\\", "/"))
        except Exception:
            pass


def main():
    App().mainloop()
