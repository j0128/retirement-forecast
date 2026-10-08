import datetime as dt
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from forecast.engine import (Account, ExtraIncome, Insurance, Loan, Property, Settings, Stage,
                             simulate_scenarios, stage_at, annuity_payment, from_dict,
                             labor_insurance_monthly, simulate, to_dict, parse_ym)

TODAY = dt.date(2026, 1, 15)


def base(**kw):
    s = Settings(current_age=30, retire_age=60, life_expectancy=90, salary_net=0, salary_withheld=0,
                 income_growth=0, income_tax_rate=0, medical_monthly=0, monthly_expense=0, retire_expense=0,
                 inflation=0, lp_enabled=False, li_enabled=False, savings_rate=0, bucket_amount=0)
    for k, v in kw.items():
        setattr(s, k, v)
    return s


class EngineTests(unittest.TestCase):
    def test_compound_growth(self):
        s = base(accounts=[Account.simple("a", 100_000, 0, 6, 100)], life_expectancy=40, retire_age=40)
        r = simulate(s, TODAY)
        self.assertAlmostEqual(r.rows[-1].net_worth, 100_000 * 1.06 ** 10, delta=1)

    def test_monthly_add_stops_after_years(self):
        s = base(accounts=[Account.simple("a", 0, 1000, 0, 2, 30)], life_expectancy=40, retire_age=40, salary_net=1000)
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
                 lp_claim_age=60, lp_lump_sum=True, life_expectancy=70,
                 lump_stages=[Stage(0, 120, 0, 0)])
        r = simulate(s, TODAY)
        self.assertAlmostEqual(r.lp_at_claim, 1_000_000, delta=1)
        self.assertEqual(r.account_names, ["退休金帳戶"])
        self.assertAlmostEqual(r.rows[-1].account_balances[0], 1_000_000, delta=1)

    def test_monthly_labor_pension_exhausts_at_end(self):
        s = base(lp_enabled=True, lp_balance=1_200_000, lp_return=0, lp_employer_pct=0,
                 lp_claim_age=60, life_expectancy=70, lp_lump_sum=False)
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
        s = base(accounts=[Account.simple("a", 100_000, 0, 10, 100)], gains_tax_rate=50, life_expectancy=31, retire_age=31)
        r = simulate(s, TODAY)
        self.assertAlmostEqual(r.rows[-1].net_worth, 105_000, delta=300)

    def test_stage_lookup(self):
        st = [Stage(30, 40, 8, 100), Stage(40, 50, 4, 50)]
        self.assertEqual(stage_at(st, 35), (8, 100))
        self.assertEqual(stage_at(st, 40), (4, 50))
        self.assertEqual(stage_at(st, 60), (4, 0))   # 最後一段之後：沿用報酬、停止加碼
        self.assertEqual(stage_at(st, 20), (8, 0))   # 第一段之前

    def test_staged_returns(self):
        st = [Stage(30, 35, 10, 0), Stage(35, 40, 0, 0)]
        s = base(accounts=[Account("a", 100_000, st)], life_expectancy=40, retire_age=40)
        r = simulate(s, TODAY)
        self.assertAlmostEqual(r.rows[-1].account_balances[0], 100_000 * 1.1 ** 5, delta=5)

    def test_staged_monthly_add(self):
        st = [Stage(30, 31, 0, 1000), Stage(31, 32, 0, 2000)]
        s = base(accounts=[Account("a", 0, st)], life_expectancy=40, retire_age=40, salary_net=5000)
        r = simulate(s, TODAY)
        self.assertAlmostEqual(r.rows[-1].account_balances[0], 12_000 + 24_000, delta=1)

    def test_old_account_format_migrates(self):
        d = {"current_age": 40, "accounts": [{"name": "舊", "cash": 10, "monthly_add": 5,
                                              "annual_return": 6, "years": 7}]}
        a = from_dict(d).accounts[0]
        self.assertEqual((a.stages[0].start_age, a.stages[0].end_age, a.stages[0].annual_return,
                          a.stages[0].monthly_add), (40, 47, 6, 5))

    def test_bucket_funded_from_investments(self):
        # 退休後每年從投資帳戶撥 1 年份生活費到生活費帳戶
        s = base(retire_age=30, retire_expense=10_000, bucket_amount=120_000, life_expectancy=40,
                 accounts=[Account("a", 5_000_000, [Stage(0, 120, 0, 0)])])
        r = simulate(s, TODAY)
        self.assertAlmostEqual(r.rows[0].bucket, 120_000, delta=1)  # 年底已補足下一年
        self.assertAlmostEqual(r.rows[0].account_balances[0], 5_000_000 - 240_000, delta=1)
        self.assertAlmostEqual(r.rows[-1].net_worth, 5_000_000 - 120_000 * 10, delta=1)
        self.assertIsNone(r.depleted_age)

    def test_bucket_default_and_inflation(self):
        self.assertEqual(Settings().bucket_amount, 1_800_000)
        s = base(retire_age=30, retire_expense=0, bucket_amount=100_000, inflation=10, life_expectancy=33,
                 accounts=[Account("a", 5_000_000, [Stage(0, 120, 0, 0)])])
        r = simulate(s, TODAY)
        self.assertAlmostEqual(r.rows[0].bucket, 110_000, delta=1)   # 第 2 年年初補到 100k×1.1

    def test_bucket_pension_flows_through(self):
        s = base(current_age=65, retire_age=65, retire_expense=10_000, bucket_amount=120_000, life_expectancy=70,
                 li_enabled=True, li_manual_monthly=10_000, li_claim_age=65,
                 accounts=[Account("a", 1_000_000, [Stage(0, 120, 0, 0)])])
        r = simulate(s, TODAY)
        self.assertAlmostEqual(r.rows[-1].net_worth, 1_000_000, delta=1)  # 年金正好支應生活費

    def test_employer_lump_goes_to_retirement_account(self):
        s = base(employer_lump=2_000_000, lump_stages=[Stage(0, 120, 0, 0)], life_expectancy=70)
        r = simulate(s, TODAY)
        self.assertEqual(r.account_names, ["退休金帳戶"])
        self.assertAlmostEqual(r.rows[-1].account_balances[0], 2_000_000, delta=1)
        self.assertAlmostEqual(r.retire_net_worth, 2_000_000, delta=1)

    def test_employer_lump_with_labor_pension_lump(self):
        s = base(employer_lump=1_000_000, lp_enabled=True, lp_balance=500_000, lp_return=0, lp_employer_pct=0,
                 lp_claim_age=60, lp_lump_sum=True, lump_stages=[Stage(0, 120, 0, 0)], life_expectancy=70)
        r = simulate(s, TODAY)
        self.assertAlmostEqual(r.rows[-1].account_balances[0], 1_500_000, delta=1)

    def test_tax_settlement_each_may(self):
        s = base(current_age=30, retire_age=35, life_expectancy=36, salary_net=50_000, salary_withheld=5_000,
                 income_tax_rate=15, savings_cash=1_000_000)
        r = simulate(s, TODAY)  # 2026-01 起：2026~2030 五個年度，於 2027~2031 年 5 月結算
        self.assertAlmostEqual(sum(x.tax_settle for x in r.rows), -5 * (0.15 * 55_000 * 12 - 60_000), delta=1)

    def test_tax_refund_when_overwithheld(self):
        s = base(current_age=30, retire_age=32, life_expectancy=34, salary_net=50_000, salary_withheld=10_000,
                 income_tax_rate=5, savings_cash=1_000_000)
        r = simulate(s, TODAY)
        self.assertGreater(sum(x.tax_settle for x in r.rows), 0)

    def test_extra_income_and_taxability(self):
        ex = ExtraIncome("兼職", 1_000, "month", 30, 32, 0, True)
        s = base(current_age=30, retire_age=40, life_expectancy=41, extra_incomes=[ex], income_tax_rate=10)
        r = simulate(s, TODAY)
        self.assertAlmostEqual(sum(x.extra_income for x in r.rows), 24_000, delta=1)
        # 應稅：2026、2027 年各課 12,000×10% = 1,200，皆於隔年 5 月補稅
        self.assertAlmostEqual(sum(x.tax_settle for x in r.rows), -2_400, delta=1)
        ex.taxable = False
        r2 = simulate(s, TODAY)
        self.assertAlmostEqual(sum(x.tax_settle for x in r2.rows), 0, delta=1)

    def test_extra_income_yearly_and_growth(self):
        ex = ExtraIncome("租金", 120_000, "year", 30, 32, 10, False)
        s = base(current_age=30, retire_age=40, life_expectancy=41, extra_incomes=[ex])
        r = simulate(s, TODAY)
        self.assertGreater(sum(x.extra_income for x in r.rows), 240_000)

    def test_insurance_premiums_and_payout(self):
        monthly = Insurance("醫療險", 1_000, "month", 30, 31)
        yearly = Insurance("儲蓄險", 12_000, "year", 30, 33, payout=50_000, payout_age=33, payout_to="a")
        s = base(current_age=30, retire_age=40, life_expectancy=41, savings_cash=1_000_000,
                 accounts=[Account("a", 0, [Stage(0, 120, 0, 0)])], insurances=[monthly, yearly])
        r = simulate(s, TODAY)
        self.assertAlmostEqual(sum(x.insurance for x in r.rows), 12_000 + 36_000, delta=1)
        self.assertAlmostEqual(r.rows[-1].account_balances[0], 50_000, delta=1)  # 滿期金入指定帳戶

    def test_property_value_sale_and_loan_payoff(self):
        loan = Loan("房貸", "amort", principal=2_000_000, annual_rate=0, start="2026-01", end="2045-12")
        prop = Property("自宅", 10_000_000, 0, sell_age=40, sell_cost=10, loan_name="房貸")
        s = base(current_age=30, retire_age=60, life_expectancy=60, loans=[loan], properties=[prop])
        r = simulate(s, TODAY)
        self.assertAlmostEqual(r.rows[0].property_value, 10_000_000, delta=1)
        self.assertLess(r.rows[0].net_worth - r.rows[0].liquid_net_worth, 10_000_001)
        row = [x for x in r.rows if x.age == 41][0]
        self.assertEqual(row.property_value, 0)
        self.assertAlmostEqual(row.loan_balance, 0, delta=1)  # 貸款已隨出售還清
        # 售屋款 = 1,000 萬 × 90% − 貸款餘額（出售當下），其餘月付已付
        paid_before = 2_000_000 / 240 * 120   # 10 年月付（零利率）
        self.assertAlmostEqual(row.free_cash, 9_000_000 - (2_000_000 - paid_before) - paid_before, delta=50)

    def test_medical_after_70(self):
        s = base(current_age=65, retire_age=65, life_expectancy=75, medical_monthly=1_000, medical_growth=0,
                 savings_cash=1_000_000)
        r = simulate(s, TODAY)
        self.assertAlmostEqual(sum(x.medical for x in r.rows), 60_000, delta=1)

    def test_scenarios_ordering(self):
        s = base(accounts=[Account.simple("a", 1_000_000, 0, 6, 100)], life_expectancy=40, retire_age=40,
                 scenario_delta=2)
        res = simulate_scenarios(s, TODAY)
        self.assertLess(res["悲觀"].rows[-1].net_worth, res["基準"].rows[-1].net_worth)
        self.assertLess(res["基準"].rows[-1].net_worth, res["樂觀"].rows[-1].net_worth)
        self.assertAlmostEqual(res["樂觀"].rows[-1].net_worth, 1_000_000 * 1.08 ** 10, delta=5)

    def test_old_income_format_migrates(self):
        d = from_dict({"monthly_income": 100_000, "income_tax_rate": 5})
        self.assertAlmostEqual(d.salary_net, 95_000)
        self.assertAlmostEqual(d.salary_withheld, 5_000)

    def test_new_lists_roundtrip(self):
        s = base(extra_incomes=[ExtraIncome()], insurances=[Insurance()], properties=[Property()])
        self.assertEqual(to_dict(s), to_dict(from_dict(to_dict(s))))

    def test_roundtrip_and_validation(self):
        s = base(accounts=[Account.simple("a", 1, 2, 3, 4)], loans=[Loan("x", start="2020-01", end="2030-01")])
        s2 = from_dict(to_dict(s))
        self.assertEqual(to_dict(s), to_dict(s2))
        with self.assertRaises(ValueError):
            simulate(base(current_age=95), TODAY)
        self.assertEqual(parse_ym("2026-03"), 2026 * 12 + 2)


if __name__ == "__main__":
    unittest.main()
