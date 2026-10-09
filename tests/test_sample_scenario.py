"""以 samples/ 內的範例情境做回歸測試（47 歲、55 歲退休）。"""
import datetime as dt
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from forecast.engine import from_dict, simulate, simulate_scenarios

PATH = os.path.join(os.path.dirname(__file__), "..", "samples", "範例_47歲_55歲退休.json")
TODAY = dt.date(2026, 10, 9)


class SampleScenario(unittest.TestCase):
    def setUp(self):
        with open(PATH, encoding="utf-8") as f:
            self.s = from_dict(json.load(f))

    def test_monthly_cashflow_matches_hand_calculation(self):
        r = simulate(self.s, TODAY)
        # 收入 175,000 − 生活 20,000 − 固定 40,000 − 旅遊 12,500 − 稅務 4,167 − 保險 5,000 − 房貸 ≈33,224 − 投資 50,000
        self.assertAlmostEqual(r.monthly_surplus_now, 10_000, delta=1_000)   # 支出隨通膨，第一年平均略低於 1 萬

    def test_base_scenario_lasts_to_life_expectancy(self):
        r = simulate(self.s, TODAY)
        self.assertIsNone(r.depleted_age)
        self.assertGreater(r.rows[-1].liquid_net_worth, 0)

    def test_pessimistic_scenario_depletes_late(self):
        res = simulate_scenarios(self.s, TODAY)
        self.assertIsNotNone(res["悲觀"].depleted_age)
        self.assertGreater(res["悲觀"].depleted_age, 75)
        self.assertIsNone(res["樂觀"].depleted_age)

    def test_bucket_is_fixed_two_million_after_retirement(self):
        r = simulate(self.s, TODAY)
        row = [x for x in r.rows if x.age == 60][0]
        self.assertAlmostEqual(row.bucket, 2_000_000, delta=1)

    def test_lump_sums_enter_retirement_account(self):
        r = simulate(self.s, TODAY)
        self.assertIn("退休金帳戶", r.account_names)
        row = [x for x in r.rows if x.age == 56][0]
        lump = row.account_balances[r.account_names.index("退休金帳戶")]
        self.assertGreater(lump, 5_000_000 + 2_000_000)   # 專戶約 961 萬 + 雇主 200 萬


if __name__ == "__main__":
    unittest.main()
