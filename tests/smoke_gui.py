"""在有桌面的環境(CI Windows)確認 GUI 能啟動、各對話框可確定、並完成一次試算。"""
import os
import sys
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from tkinter import messagebox

from forecast.engine import Account, ExtraExpense, ExtraIncome, Insurance, Loan, OneOff, Property
import forecast.gui as gui
from forecast.gui import App

errors = []
messagebox.showerror = lambda *a, **k: errors.append(a)
gui.settings_path = lambda: os.path.join(os.path.dirname(__file__), "_smoke_settings.json")
app = App()
app.s.accounts = [Account.simple("股票", 500000, 20000, 6, 20, 35)]
app.s.loans = [Loan("房貸", "amort", principal=8_000_000, annual_rate=2.2, start="2024-01", end="2054-01")]
app.s.properties = [Property("自宅", 12_000_000, 2, 65, 4, "房貸", "")]
app.s.insurances = [Insurance("儲蓄險", 60000, "year", 35, 50, False, 1_000_000, 50, "股票")]
app.s.extra_incomes = [ExtraIncome("兼職", 10000, "month", 35, 60, 0, True)]
app.s.extra_expenses = [ExtraExpense("子女教育", 240000, "year", 35, 50)]
app.s.one_offs = [OneOff("購車", "out", 600000, 40), OneOff("遺產", "in", 1000000, 60, "股票")]
app.s.bonus_months = 2
app.s.lp_lump_sum = True
app._to_form()
app.update()


def press_ok():
    for w in app.winfo_children():
        if isinstance(w, tk.Toplevel):
            w._ok()


for fn, item in ((app._ins_dialog, app.s.insurances[0]), (app._prop_dialog, app.s.properties[0]),
                 (app._extra_dialog, app.s.extra_incomes[0]), (app._acc_dialog, app.s.accounts[0]),
                 (app._loan_dialog, app.s.loans[0]), (app._xexp_dialog, app.s.extra_expenses[0]),
                 (app._oneoff_dialog, app.s.one_offs[0])):
    app.after(300, press_ok)
    assert fn(item) is not None, fn.__name__

for key, _ in app.NAV:
    app.show(key)
    app.update()
for key in ("basic", "income", "res"):
    app.show(key)
    app.update()
    app.pages[key].scroll(5)
    app.pages[key].scroll(-5)
app.calculate()
app.update()
assert not errors, errors
assert app.results and set(app.results) == {"悲觀", "基準", "樂觀"}
assert app.result.account_names[-1] == "退休金帳戶", app.result.account_names
assert app.res_tree.get_children(), "no result rows"
for scn in ("悲觀", "樂觀"):
    app.table_scn.set(scn)
    app._fill_table()
app.show_prop.set(False)
app.show_real.set(True)
app._draw_chart()
app.update()
app.destroy()
try:
    os.remove(os.path.join(os.path.dirname(__file__), "_smoke_settings.json"))
except OSError:
    pass
print("GUI smoke OK")
