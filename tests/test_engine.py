import datetime as dt
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from forecast.engine import (Account, Loan, Settings, annuity_payment, from_dict,
                             labor_insurance_monthly, simulate, to_dict, parse_ym)

TODAY = dt.date(2026, 1, 15)


def base(**kw):
    s = Settings(current_age=30, retire_age=60, life_expectancy=90, monthly_income=0,
                 income_growth=0, income_tax_rate=0, monthly_expense=0, retire_expense=0,
                 inflation=0, lp_enabled=False, li_enabled=False, savings_rate=0)
    for k, v in kw.items():
        setattr(s, k, v)
    return s


class EngineTests(unittest.TestCase):
    def test_compound_growth(self):
        s = base(accounts=[Account("a", 100_000, 0, 6, 0)], life_expectancy=40, retire_age=40)
        r = simulate(s, TODAY)
        self.assertAlmostEqual(r.rows[-1].net_worth, 100_000 * 1.06 ** 10, delta=1)

    def test_monthly_add_stops_after_years(self):
        s = base(accounts=[Account("a", 0, 1000, 0, 2)], life_expectancy=40, retire_age=40, monthly_income=1000)
        r = simulate(s, TODAY)
        self.assertAlmostEqual(sum(r.rows[-1].account_balances), 24_000, delta=1)

    def test_amort_loan_pays_off(self):
        s = base(life_expectancy=70, savings_cash=0, loans=[
            Loan("房貸", "amort", principal=1_000_000, annual_rate=2, start="2026-01", end="2045-12")])
        r = simulate(s, TODAY)
        # 20 年後貸款餘額為 0
        row = [x for x in r.rows if x.age == 50][0]
        self.assertAlmostEqual(row.loan_balance, 0, delta=1)
        pay = annuity_payment(1_000_000, 2, 240)
        self.assertAlmostEqual(r.rows[0].loan_paid, pay * 12, delta=1)

    def test_amort_loan_started_in_past(self):
        s = base(loans=[Loan("房貸", "amort", principal=1_000_000, annual_rate=2,
                             start="2016-01", end="2045-12")])
        r = simulate(s, TODAY)
        self.assertGreater(r.rows[0].loan_balance, 0)
        self.assertLess(r.rows[0].loan_balance, 1_000_000)

    def test_fixed_loan_window(self):
        s = base(loans=[Loan("車貸", "fixed", monthly_payment=10_000, start="2026-01", end="2026-12")])
        r = simulate(s, TODAY)
        self.assertAlmostEqual(r.rows[0].loan_paid, 120_000, delta=1)
        self.assertAlmostEqual(r.rows[1].loan_paid, 0, delta=1)

    def test_lump_sum_labor_pension(self):
        s = base(lp_enabled=True, lp_balance=1_000_000, lp_return=0, lp_employer_pct=0,
                 lp_claim_age=60, lp_lump_sum=True, life_expectancy=70)
        r = simulate(s, TODAY)
        self.assertAlmostEqual(r.lp_at_claim, 1_000_000, delta=1)
        self.assertAlmostEqual(r.rows[-1].free_cash, 1_000_000, delta=1)

    def test_monthly_labor_pension_exhausts_at_end(self):
        s = base(lp_enabled=True, lp_balance=1_200_000, lp_return=0, lp_employer_pct=0,
                 lp_claim_age=60, life_expectancy=70)
        r = simulate(s, TODAY)
        self.assertAlmostEqual(r.lp_monthly, 10_000, delta=1)
        self.assertAlmostEqual(r.rows[-1].lp_balance, 0, delta=1)

    def test_labor_insurance_formula(self):
        s = base(li_enabled=True, li_avg_wage=40_000, li_years_now=20, current_age=40,
                 retire_age=60, li_claim_age=65)
        # 年資 40：B = 40000*40*1.55% = 24800；A = 40000*40*0.775%+3000 = 15400
        self.assertAlmostEqual(labor_insurance_monthly(s), 24_800, delta=1)
        s.li_claim_age = 70
        self.assertAlmostEqual(labor_insurance_monthly(s), 24_800 * 1.2, delta=1)

    def test_depletion_detected(self):
        s = base(retire_age=60, retire_expense=50_000, savings_cash=1_000_000, life_expectancy=90)
        r = simulate(s, TODAY)
        self.assertIsNotNone(r.depleted_age)
        self.assertAlmostEqual(r.depleted_age, 60 + 1_000_000 / 50_000 / 12, delta=1)

    def test_real_value_discount(self):
        s = base(savings_cash=1_000_000, savings_rate=0, inflation=2, life_expectancy=40, retire_age=40)
        r = simulate(s, TODAY)
        self.assertAlmostEqual(r.rows[-1].real_net_worth, 1_000_000 / 1.02 ** 10, delta=5)

    def test_gains_tax(self):
        s = base(accounts=[Account("a", 100_000, 0, 10, 0)], gains_tax_rate=50, life_expectancy=31, retire_age=31)
        r = simulate(s, TODAY)
        self.assertAlmostEqual(r.rows[-1].net_worth, 105_000, delta=300)

    def test_roundtrip_and_validation(self):
        s = base(accounts=[Account("a", 1, 2, 3, 4)], loans=[Loan("x", start="2020-01", end="2030-01")])
        s2 = from_dict(to_dict(s))
        self.assertEqual(to_dict(s), to_dict(s2))
        with self.assertRaises(ValueError):
            simulate(base(current_age=95), TODAY)
        self.assertEqual(parse_ym("2026-03"), 2026 * 12 + 2)


if __name__ == "__main__":
    unittest.main()
