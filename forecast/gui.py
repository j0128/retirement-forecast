"""tkinter 圖形介面。"""
from __future__ import annotations

import csv
import datetime as dt
import json
import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .engine import Account, Loan, Result, Settings, Stage, from_dict, simulate, to_dict


def settings_path() -> str:
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) \
        else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "retirement_settings.json")


def money(v: float) -> str:
    return f"{v:,.0f}"


class FormDialog(tk.Toplevel):
    """通用欄位輸入對話框。fields: [(key, label, kind, default, choices)]"""

    def __init__(self, parent, title, fields):
        super().__init__(parent)
        self.title(title)
        self.transient(parent)
        self.resizable(False, False)
        self.result = None
        self.vars = {}
        self.fields = fields
        for r, (key, label, kind, default, *rest) in enumerate(fields):
            ttk.Label(self, text=label).grid(row=r, column=0, sticky="e", padx=8, pady=4)
            if kind == "choice":
                var = tk.StringVar(value=default)
                w = ttk.Combobox(self, textvariable=var, values=rest[0], state="readonly", width=22)
            else:
                var = tk.StringVar(value=str(default))
                w = ttk.Entry(self, textvariable=var, width=24)
            w.grid(row=r, column=1, padx=8, pady=4)
            self.vars[key] = var
        bar = ttk.Frame(self)
        bar.grid(row=len(fields), column=0, columnspan=2, pady=8)
        ttk.Button(bar, text="確定", command=self._ok).pack(side="left", padx=6)
        ttk.Button(bar, text="取消", command=self.destroy).pack(side="left", padx=6)
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
        self.transient(parent)
        self.show_add = show_add
        self.stages = [Stage(**vars(st)) for st in stages]
        self.result = None
        self.name_var = tk.StringVar(value=name or "")
        self.cash_var = tk.StringVar(value=f"{cash:g}" if cash is not None else "")
        r = 0
        if name is not None:
            ttk.Label(self, text="帳戶名稱").grid(row=r, column=0, sticky="e", padx=8, pady=4)
            ttk.Entry(self, textvariable=self.name_var, width=24).grid(row=r, column=1, sticky="w")
            r += 1
            ttk.Label(self, text="目前現金/本金").grid(row=r, column=0, sticky="e", padx=8, pady=4)
            ttk.Entry(self, textvariable=self.cash_var, width=24).grid(row=r, column=1, sticky="w")
            r += 1
        cols = ("start", "end", "ret") + (("add",) if show_add else ())
        heads = ("起始年齡", "結束年齡", "年均報酬 %") + (("每月增額",) if show_add else ())
        self.tree = ttk.Treeview(self, columns=cols, show="headings", height=6, selectmode="browse")
        for c, h in zip(cols, heads):
            self.tree.heading(c, text=h)
            self.tree.column(c, width=110, anchor="center")
        self.tree.grid(row=r, column=0, columnspan=2, padx=8, pady=6)
        self.tree.bind("<Double-1>", lambda e: self.edit())
        bar = ttk.Frame(self)
        bar.grid(row=r + 1, column=0, columnspan=2)
        for text, cmd in (("新增時間段", self.add), ("編輯", self.edit), ("刪除", self.delete)):
            ttk.Button(bar, text=text, command=cmd).pack(side="left", padx=4)
        ttk.Label(self, foreground="gray", justify="left", text=(
            "時間段含起始、不含結束年齡。最後一段結束後沿用最後一段的報酬率，並停止加碼。\n"
            "每月增額僅在退休前有效。")).grid(row=r + 2, column=0, columnspan=2, padx=8, pady=4)
        ok = ttk.Frame(self)
        ok.grid(row=r + 3, column=0, columnspan=2, pady=8)
        ttk.Button(ok, text="確定", command=self._ok).pack(side="left", padx=6)
        ttk.Button(ok, text="取消", command=self.destroy).pack(side="left", padx=6)
        self._refresh()
        self.grab_set()
        self.wait_window()

    def _refresh(self):
        self.stages.sort(key=lambda x: x.start_age)
        self.tree.delete(*self.tree.get_children())
        for st in self.stages:
            vals = [f"{st.start_age:g}", f"{st.end_age:g}", f"{st.annual_return:g}"]
            if self.show_add:
                vals.append(money(st.monthly_add))
            self.tree.insert("", "end", values=vals)

    def _dialog(self, st):
        fields = [("start_age", "起始年齡", "num", st.start_age), ("end_age", "結束年齡", "num", st.end_age),
                  ("annual_return", "年均報酬率 %", "num", st.annual_return)]
        if self.show_add:
            fields.append(("monthly_add", "每月增額", "num", st.monthly_add))
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


def stage_summary(stages) -> str:
    return "；".join(f"{st.start_age:g}-{st.end_age:g}歲 {st.annual_return:g}%"
                    + (f" 加碼{money(st.monthly_add)}" if st.monthly_add else "")
                    for st in sorted(stages, key=lambda x: x.start_age)) or "（未設定）"


class App(tk.Tk):
    BASIC = [
        ("current_age", "目前年齡"), ("retire_age", "預期退休年齡"), ("life_expectancy", "預期壽命（試算到幾歲）"),
        ("monthly_income", "月均收入（稅前, NT$）"), ("income_growth", "每年調薪 %"),
        ("income_tax_rate", "所得稅有效稅率 %"),
        ("monthly_expense", "目前每月生活支出（今日幣值）"), ("retire_expense", "退休後每月生活支出（今日幣值）"),
        ("inflation", "通膨率 % / 年"), ("gains_tax_rate", "投資獲利稅率 %"),
        ("savings_cash", "活存現金（未投入）"), ("savings_rate", "活存年利率 %"),
        ("bucket_amount", "退休後生活費帳戶：每年年初補足金額（今日幣值）"),
    ]
    LP = [
        ("lp_wage", "提繳工資（0 = 取月收入）"), ("lp_wage_cap", "提繳工資上限"),
        ("lp_employer_pct", "雇主/學校提繳 %"),
        ("lp_self_pct", "個人提繳 %（自提）"), ("lp_balance", "退休金專戶現有餘額"),
        ("lp_return", "專戶年收益率 %（累積期與月領期）"),
        ("lp_claim_age", "請領年齡（不早於退休年齡；私校帳戶可退休即領）"),
    ]
    LI = [
        ("li_avg_wage", "平均月投保薪資"), ("li_years_now", "目前已投保年資（年）"),
        ("li_claim_age", "勞保年金請領年齡（60~70）"),
        ("li_manual_monthly", "或直接輸入預估月領金額（>0 則採用）"),
    ]

    def __init__(self):
        super().__init__()
        self.title("退休收益預測")
        self.geometry("1100x720")
        self.s = Settings()
        self.result: Result | None = None
        self.vars: dict[str, tk.Variable] = {}
        self.show_real = tk.BooleanVar(value=False)
        self._build()
        self._load_auto()

    # ---------- UI ----------
    def _build(self):
        bar = ttk.Frame(self)
        bar.pack(fill="x", padx=8, pady=6)
        ttk.Button(bar, text="▶ 開始試算", command=self.calculate).pack(side="left")
        ttk.Button(bar, text="儲存設定", command=self.save_as).pack(side="left", padx=4)
        ttk.Button(bar, text="載入設定", command=self.load_from).pack(side="left")
        ttk.Button(bar, text="匯出 CSV", command=self.export_csv).pack(side="left", padx=4)
        ttk.Checkbutton(bar, text="圖表/表格以實質購買力（扣除通膨）顯示",
                        variable=self.show_real, command=self._render).pack(side="left", padx=12)
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=8, pady=4)
        self.tab_basic = ttk.Frame(self.nb)
        self.tab_acc = ttk.Frame(self.nb)
        self.tab_loan = ttk.Frame(self.nb)
        self.tab_pen = ttk.Frame(self.nb)
        self.tab_res = ttk.Frame(self.nb)
        for t, n in ((self.tab_basic, "基本資料"), (self.tab_acc, "投資帳戶"), (self.tab_loan, "房貸/貸款"),
                     (self.tab_pen, "勞退 / 勞保"), (self.tab_res, "結果")):
            self.nb.add(t, text=n)
        self._grid_form(self.tab_basic, self.BASIC)
        self._build_pension()
        self.acc_tree = self._list_tab(
            self.tab_acc, ("name", "cash", "stages"),
            ("帳戶名稱", "現金/本金", "投資時間段（年齡 / 報酬 / 加碼）"),
            self.add_account, self.edit_account, self.del_account, reorder=self.move_account)
        self.acc_tree.column("stages", width=560, anchor="w")
        self.loan_tree = self._list_tab(
            self.tab_loan, ("name", "mode", "pay", "start", "end"),
            ("名稱", "方式", "每月扣款/本金", "起（YYYY-MM）", "迄（YYYY-MM）"),
            self.add_loan, self.edit_loan, self.del_loan)
        self._build_results()

    def _grid_form(self, parent, fields, row0=0):
        for i, (key, label) in enumerate(fields):
            ttk.Label(parent, text=label).grid(row=row0 + i, column=0, sticky="e", padx=8, pady=5)
            v = tk.StringVar()
            ttk.Entry(parent, textvariable=v, width=18).grid(row=row0 + i, column=1, sticky="w", pady=5)
            self.vars[key] = v

    def _build_pension(self):
        f = self.tab_pen
        self.vars["lp_enabled"] = tk.BooleanVar()
        self.vars["lp_lump_sum"] = tk.StringVar()
        self.vars["li_enabled"] = tk.BooleanVar()
        ttk.Checkbutton(f, text="計入退休金專戶（勞退新制 / 私校退撫儲金等；比例請依薪資單設定）", variable=self.vars["lp_enabled"]).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=8, pady=6)
        self._grid_form(f, self.LP, 1)
        r = 1 + len(self.LP)
        ttk.Label(f, text="領取方式").grid(row=r, column=0, sticky="e", padx=8)
        ttk.Combobox(f, textvariable=self.vars["lp_lump_sum"], values=["月領", "一次領"],
                     state="readonly", width=15).grid(row=r, column=1, sticky="w")
        ttk.Button(f, text="設定「退休金帳戶」投資階段（一次領後的投資）",
                   command=self.edit_lump_stages).grid(row=r, column=2, padx=8, sticky="w")
        ttk.Checkbutton(f, text="計入勞保老年年金（65 歲起；提前/延後每年 ∓4%，最多 5 年）",
                        variable=self.vars["li_enabled"]).grid(row=r + 1, column=0, columnspan=2,
                                                               sticky="w", padx=8, pady=(16, 6))
        self._grid_form(f, self.LI, r + 2)
        ttk.Label(f, foreground="gray", justify="left", text=(
            "勞保年金公式：年資 ×（平均投保薪資 × 0.775% + 3,000）與（平均投保薪資 × 1.55%）取高者。\n"
            "年資 = 目前年資 + 到退休前繼續投保的年數。平均月投保薪資上限以現行規定為準，請自行調整。\n"
            "本工具為估算，不代表實際給付金額。")).grid(
            row=r + 8, column=0, columnspan=3, sticky="w", padx=8, pady=14)

    def _list_tab(self, parent, cols, heads, add, edit, delete, reorder=None):
        tree = ttk.Treeview(parent, columns=cols, show="headings", height=10, selectmode="browse")
        for c, h in zip(cols, heads):
            tree.heading(c, text=h)
            tree.column(c, width=150, anchor="center")
        tree.pack(fill="both", expand=True, padx=8, pady=8)
        bar = ttk.Frame(parent)
        bar.pack(fill="x", padx=8, pady=(0, 8))
        ttk.Button(bar, text="新增", command=add).pack(side="left")
        ttk.Button(bar, text="編輯", command=edit).pack(side="left", padx=4)
        ttk.Button(bar, text="刪除", command=delete).pack(side="left")
        if reorder:
            ttk.Button(bar, text="上移", command=lambda: reorder(-1)).pack(side="left", padx=(16, 4))
            ttk.Button(bar, text="下移", command=lambda: reorder(1)).pack(side="left")
            ttk.Label(bar, foreground="gray", text="（退休後依清單順序由上而下提領）").pack(side="left", padx=8)
        tree.bind("<Double-1>", lambda e: edit())
        return tree

    def _build_results(self):
        self.summary = tk.Text(self.tab_res, height=7, wrap="word", font=("Microsoft JhengHei", 11))
        self.summary.pack(fill="x", padx=8, pady=6)
        self.canvas = tk.Canvas(self.tab_res, height=280, bg="white", highlightthickness=1,
                                highlightbackground="#ccc")
        self.canvas.pack(fill="x", padx=8)
        self.canvas.bind("<Configure>", lambda e: self._draw_chart())
        self.res_tree = ttk.Treeview(self.tab_res, show="headings", height=10)
        sb = ttk.Scrollbar(self.tab_res, command=self.res_tree.yview)
        self.res_tree.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y", pady=6)
        self.res_tree.pack(fill="both", expand=True, padx=(8, 0), pady=6)

    # ---------- 資料 <-> 表單 ----------
    def _to_form(self):
        s = self.s
        for key, v in self.vars.items():
            val = getattr(s, key)
            if key == "lp_lump_sum":
                v.set("一次領" if val else "月領")
            elif isinstance(v, tk.BooleanVar):
                v.set(bool(val))
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
                    raise ValueError(f"「{key}」不是有效數字：{raw}")
        return s

    def _refresh_lists(self):
        self.acc_tree.delete(*self.acc_tree.get_children())
        for a in self.s.accounts:
            self.acc_tree.insert("", "end", values=(a.name, money(a.cash), stage_summary(a.stages)))
        self.loan_tree.delete(*self.loan_tree.get_children())
        for l in self.s.loans:
            if l.mode == "amort":
                mode, amt = f"本息平均攤還 {l.annual_rate:g}%", money(l.principal)
            else:
                mode, amt = "固定月扣款", money(l.monthly_payment)
            end = l.end or f"(+{l.years:g} 年)"
            self.loan_tree.insert("", "end", values=(l.name, mode, amt, l.start, end))

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

    def _loan_dialog(self, l: Loan | None):
        l = l or Loan(start=dt.date.today().strftime("%Y-%m"))
        names = ["固定月扣款", "本息平均攤還（輸入本金與利率）"]
        d = FormDialog(self, "房貸/貸款", [
            ("name", "名稱", "text", l.name),
            ("mode", "計算方式", "choice", names[1] if l.mode == "amort" else names[0], names),
            ("monthly_payment", "每月扣款（固定月扣款用）", "num", l.monthly_payment),
            ("principal", "原貸款金額（攤還用）", "num", l.principal),
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

    def _val(self, row, attr):
        return getattr(row, attr)

    def _render(self):
        r = self.result
        if not r:
            return
        s = self.s
        end_row = r.rows[-1]
        lines = [
            f"{int(s.retire_age)} 歲退休時淨資產：NT$ {money(r.retire_net_worth)}"
            f"（約合今日購買力 NT$ {money(r.retire_real_net_worth)}）",
            f"{int(s.life_expectancy)} 歲時淨資產：NT$ {money(end_row.net_worth)}"
            f"（今日購買力 NT$ {money(end_row.real_net_worth)}）",
            ("資產耗盡年齡：約 %.1f 歲 ⚠" % r.depleted_age) if r.depleted_age
            else f"資產可支撐到 {int(s.life_expectancy)} 歲 ✔",
            f"勞保年金估計每月 NT$ {money(r.li_monthly)}；退休金專戶"
            + (f"一次領 NT$ {money(r.lp_at_claim)}，轉入「退休金帳戶」投資" if s.lp_lump_sum
               else f"每月可領 NT$ {money(r.lp_monthly)}（請領時累積 NT$ {money(r.lp_at_claim)}）"),
            f"目前每月現金流（收入 − 支出 − 貸款 − 投資）：NT$ {money(r.monthly_surplus_now)}",
        ] + [f"⚠ {w}" for w in r.warnings]
        self.summary.config(state="normal")
        self.summary.delete("1.0", "end")
        self.summary.insert("1.0", "\n".join(lines))
        self.summary.config(state="disabled")

        cols = ["age", "income", "pension", "expense", "loan", "invest"] + \
               [f"a{i}" for i in range(len(r.account_names))] + ["free", "bucket", "lp", "debt", "nw", "real"]
        heads = ["年齡", "稅後薪資", "年金/勞退領取", "生活支出", "貸款支出", "新增投資"] + r.account_names + \
                ["活存/現金", "退休生活費帳戶", "退休金專戶", "貸款餘額", "淨資產", "淨資產(今日購買力)"]
        self.res_tree.configure(columns=cols)
        for c, h in zip(cols, heads):
            self.res_tree.heading(c, text=h)
            self.res_tree.column(c, width=100, anchor="e")
        self.res_tree.delete(*self.res_tree.get_children())
        for x in r.rows:
            self.res_tree.insert("", "end", values=[f"{x.age:g}", money(x.income), money(x.pension_income),
                                                   money(x.expense), money(x.loan_paid), money(x.invested)] +
                                 [money(b) for b in x.account_balances] +
                                 [money(x.free_cash), money(x.bucket), money(x.lp_balance), money(x.loan_balance),
                                  money(x.net_worth), money(x.real_net_worth)])
        self._draw_chart()

    def _draw_chart(self):
        c = self.canvas
        c.delete("all")
        r = self.result
        if not r or not r.rows:
            return
        w, h = c.winfo_width(), c.winfo_height()
        L, R, T, B = 80, 20, 20, 30
        series = [("名義淨資產", [x.net_worth for x in r.rows], "#2563eb"),
                  ("今日購買力", [x.real_net_worth for x in r.rows], "#16a34a")]
        if self.show_real.get():
            series = series[::-1]
        ages = [x.age for x in r.rows]
        allv = [v for _, vals, _ in series for v in vals] + [0]
        lo, hi = min(allv), max(allv)
        if hi == lo:
            hi = lo + 1
        x0, x1 = ages[0], ages[-1]

        def px(a):
            return L + (a - x0) / max(x1 - x0, 1e-9) * (w - L - R)

        def py(v):
            return T + (hi - v) / (hi - lo) * (h - T - B)
        for i in range(5):
            v = lo + (hi - lo) * i / 4
            c.create_line(L, py(v), w - R, py(v), fill="#eee")
            c.create_text(L - 6, py(v), text=f"{v / 10000:,.0f}萬", anchor="e", font=("", 8))
        c.create_line(L, py(0), w - R, py(0), fill="#888")
        step = max(1, int((x1 - x0) // 10))
        for a in ages[::step]:
            c.create_text(px(a), h - B + 12, text=f"{a:g}", font=("", 8))
        ra = self.s.retire_age
        if x0 <= ra <= x1:
            c.create_line(px(ra), T, px(ra), h - B, fill="#f59e0b", dash=(4, 3))
            c.create_text(px(ra) + 4, T + 2, text="退休", anchor="nw", fill="#f59e0b")
        for k, (name, vals, color) in enumerate(series):
            pts = [coord for a, v in zip(ages, vals) for coord in (px(a), py(v))]
            if len(pts) >= 4:
                c.create_line(*pts, fill=color, width=2)
            c.create_text(L + 10 + k * 120, h - 8, text="● " + name, fill=color, anchor="w", font=("", 9))

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
            w.writerow(["年齡", "稅後薪資", "年金/勞退領取", "生活支出", "貸款支出", "新增投資"] +
                       r.account_names + ["活存/現金", "退休生活費帳戶", "退休金專戶", "貸款餘額", "淨資產", "淨資產(今日購買力)"])
            for x in r.rows:
                w.writerow([x.age, round(x.income), round(x.pension_income), round(x.expense),
                            round(x.loan_paid), round(x.invested)] +
                           [round(b) for b in x.account_balances] +
                           [round(x.free_cash), round(x.bucket), round(x.lp_balance), round(x.loan_balance),
                            round(x.net_worth), round(x.real_net_worth)])


def main():
    App().mainloop()
