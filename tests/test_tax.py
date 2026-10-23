import datetime as dt
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from forecast import tax
from forecast.engine import ExtraIncome, Settings, simulate


class TaxTableTests(unittest.TestCase):
    def tearDown(self):
        tax.load_overrides("/nonexistent")   # 還原內建表

    def test_progressive_slices_match_official_formula(self):
        t = tax.table_for(115)
        # 淨額 100 萬：5% × 61 萬 + 12% × 39 萬 = 77,300（= 12% × 100 萬 − 累進差額 42,700）
        self.assertAlmostEqual(tax.progressive_tax(1_000_000, t.brackets)[0], 77_300, delta=0.5)
        self.assertEqual(tax.progressive_tax(1_000_000, t.brackets)[1], 12)

    def test_single_salary_115(self):
        t = tax.table_for(115)
        r = tax.income_tax(t, salary=2_000_000)
        # 淨額 = 200 萬 − 薪資扣除 22.7 萬 − 免稅額 10.1 萬 − 標準扣除 13.6 萬 = 153.6 萬
        self.assertAlmostEqual(r["net_income"], 1_536_000, delta=1)
        self.assertAlmostEqual(r["tax"], 154_100, delta=1)
        self.assertAlmostEqual(tax.income_tax(t, salary=1_000_000)["tax"], 26_800, delta=1)

    def test_married_dependents_and_70(self):
        t = tax.table_for(115)
        m = tax.income_tax(t, salary=2_000_000, married=True)
        self.assertAlmostEqual(m["exemptions"], 202_000, delta=1)
        self.assertAlmostEqual(m["deduction"], 272_000, delta=1)
        self.assertAlmostEqual(m["tax"], 113_180, delta=1)
        d = tax.income_tax(t, salary=2_000_000, dependents=2, elders=1)
        self.assertAlmostEqual(d["exemptions"], 101_000 * 3 + 151_500, delta=1)
        self.assertAlmostEqual(tax.income_tax(t, salary=0, other=1_000_000, taxpayer_70=True)["exemptions"],
                               151_500, delta=1)

    def test_salary_deduction_capped_by_salary_and_itemized_wins(self):
        t = tax.table_for(115)
        self.assertAlmostEqual(tax.income_tax(t, salary=100_000)["salary_deduction"], 100_000, delta=1)
        self.assertAlmostEqual(tax.income_tax(t, salary=2_000_000, itemized=500_000)["deduction"], 500_000, delta=1)

    def test_rent_is_taxed_after_43_percent_cost(self):
        r = tax.income_tax(tax.table_for(115), rent=1_000_000)
        self.assertAlmostEqual(r["rent_net"], 570_000, delta=1)

    def test_114_table_and_indexing(self):
        t114 = tax.table_for(114)
        self.assertEqual((t114.exemption, t114.salary_deduction), (97_000, 218_000))
        self.assertEqual(t114.brackets[0][0], 590_000)
        idx = tax.table_for(117, 2.0, True)
        self.assertAlmostEqual(idx.exemption, 101_000 * 1.02 ** 2, delta=1)
        self.assertAlmostEqual(idx.brackets[0][0], 610_000 * 1.02 ** 2, delta=1)
        self.assertEqual(tax.table_for(117, 2.0, False).exemption, 101_000)

    def test_override_file(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
            json.dump({"116": {"exemption": 105000, "exemption_70": 157500, "std_single": 141000,
                               "std_married": 282000, "salary_deduction": 235000,
                               "brackets": [[630000, 5], [1430000, 12], [None, 20]]}}, f)
            path = f.name
        try:
            self.assertEqual(tax.load_overrides(path), 1)
            t = tax.table_for(116)
            self.assertEqual(t.exemption, 105_000)
            self.assertEqual(len(t.brackets), 3)
        finally:
            os.remove(path)


class EngineBracketTax(unittest.TestCase):
    def base(self, **kw):
        s = Settings(current_age=30, retire_age=32, life_expectancy=34, salary_net=80_000, salary_withheld=0,
                     income_growth=0, inflation=0, monthly_expense=0, retire_expense=0, savings_cash=1_000_000,
                     savings_rate=0, lp_enabled=False, li_enabled=False, medical_monthly=0, bucket_amount=0,
                     tax_mode="bracket", tax_index=False)
        for k, v in kw.items():
            setattr(s, k, v)
        return s

    def test_annual_settlement_uses_official_brackets(self):
        r = simulate(self.base(), dt.date(2026, 1, 15))
        # 年薪 96 萬：淨額 = 96 − 22.7 − 10.1 − 13.6 = 49.6 萬 → 5% = 24,800；2026、2027 兩年度各結算一次
        self.assertAlmostEqual(sum(x.tax_settle for x in r.rows), -2 * 24_800, delta=2)
        self.assertAlmostEqual(r.cashflow["tax"], -24_800 / 12, delta=2)

    def test_first_partial_year_is_annualized(self):
        r = simulate(self.base(), dt.date(2026, 10, 9))
        # 2026 年只模擬 10~12 月，仍以整年度計稅：2027 年 5 月結算 2026 年度 → −24,800
        self.assertAlmostEqual(r.rows[0].tax_settle, -24_800, delta=2)

    def test_withholding_offsets_bracket_tax(self):
        r = simulate(self.base(salary_withheld=2_000), dt.date(2026, 1, 15))
        # 薪資所得 = (8 萬 + 2 千) × 12 = 98.4 萬 → 淨額 52 萬 → 26,000；已預扣 24,000
        self.assertAlmostEqual(r.rows[1].tax_settle, 24_000 - 26_000, delta=2)

    def test_rent_and_other_extras_follow_kind(self):
        ex = [ExtraIncome("租金", 100_000, "year", 30, 40, 0, True, "", "rent")]
        r = simulate(self.base(salary_net=0, extra_incomes=ex, retire_age=40, life_expectancy=41),
                     dt.date(2026, 1, 15))
        # 租金 10 萬 → 扣 43% 後 5.7 萬，低於免稅額與標準扣除額 → 不用繳稅
        self.assertAlmostEqual(sum(x.tax_settle for x in r.rows), 0, delta=1)

    def test_rate_mode_still_works(self):
        s = self.base(tax_mode="rate", income_tax_rate=10)
        r = simulate(s, dt.date(2026, 1, 15))
        self.assertAlmostEqual(r.rows[1].tax_settle, -0.10 * 960_000, delta=2)


class ReportAndSmoke(unittest.TestCase):
    def test_report_mentions_tax_mode(self):
        from forecast.engine import simulate_scenarios
        from forecast.report import build_report
        s = Settings(current_age=40, retire_age=50, life_expectancy=60, salary_net=80_000, tax_mode="bracket",
                     tax_married=True, tax_dependents=1)
        html = build_report(s, simulate_scenarios(s, dt.date(2026, 1, 15)))
        self.assertIn("台灣綜合所得稅級距", html)
        s.tax_mode = "rate"
        self.assertIn("有效稅率", build_report(s, simulate_scenarios(s, dt.date(2026, 1, 15))))


if __name__ == "__main__":
    unittest.main()
