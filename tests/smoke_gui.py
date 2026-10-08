"""在有桌面的環境(CI Windows)快速確認 GUI 能啟動並完成一次試算。"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tkinter import messagebox

from forecast.engine import Account, Loan
from forecast.gui import App

errors = []
messagebox.showerror = lambda *a, **k: errors.append(a)
app = App()
app.s.accounts = [Account.simple("股票", 500000, 20000, 6, 20, 35)]
app.s.loans = [Loan("房貸", "amort", principal=8_000_000, annual_rate=2.2, start="2024-01", end="2054-01")]
app.s.lp_lump_sum = True
app._to_form()
app.update()
app.calculate()
app.update()
assert not errors, errors
assert app.result.account_names[-1] == "退休金帳戶", app.result.account_names
assert app.result and app.res_tree.get_children(), "no result rows"
app.destroy()
print("GUI smoke OK")
