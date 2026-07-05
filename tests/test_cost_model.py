"""결정론적 원가 모델 테스트 — 보고서 숫자의 원천이므로 산술이 검증되어야 한다."""
import unittest

from src.cost_model import compute_loss


class TestCostModel(unittest.TestCase):
    def setUp(self):
        self.r = compute_loss()

    def test_identifies_worst_equipment(self):
        self.assertEqual(self.r["affected_equip"], "RTP-01")
        self.assertEqual(self.r["affected_process"], "RTP")

    def test_yield_delta_positive_and_significant(self):
        self.assertGreater(self.r["yield_loss_pp"], 3.0)

    def test_loss_arithmetic_consistent(self):
        expect = self.r["lost_wafers"] * self.r["scrap_cost_per_wafer_krw"]
        self.assertEqual(self.r["loss_krw"], expect)

    def test_lost_wafers_formula(self):
        expect = round(self.r["recent_wafers"] * self.r["yield_loss_pp"] / 100)
        self.assertEqual(self.r["lost_wafers"], expect)

    def test_assumptions_documented(self):
        self.assertGreaterEqual(len(self.r["assumptions"]), 3)

    def test_statistical_significance_gate(self):
        sig = self.r["significance"]
        self.assertTrue(sig["significant"])
        self.assertGreaterEqual(sig["sigma_multiple"], 3.0)
        self.assertGreater(sig["baseline_sigma_pp"], 0)
        self.assertEqual(len(self.r["formula"]), 4)  # 유의성 판정이 산식 1행으로 노출

    def test_target_equipment_respected(self):
        r = compute_loss(target_equip="DEP-03")
        self.assertEqual(r["affected_equip"], "DEP-03")
        self.assertGreater(r["yield_loss_pp"], 1.0)
        self.assertLess(r["yield_loss_pp"], 3.0)

    def test_target_without_drop_falls_back_to_worst(self):
        r = compute_loss(target_equip="RTP-02")  # 대조군 — 하락 없음
        self.assertEqual(r["affected_equip"], "RTP-01")

    def test_evidence_series_included(self):
        self.assertEqual(self.r["contrast_equip"], "RTP-02")
        self.assertIn("RTP-01", self.r["daily_yield"])
        self.assertIn("RTP-02", self.r["daily_yield"])
        self.assertGreaterEqual(len(self.r["daily_yield"]["RTP-01"]), 10)
        self.assertEqual(len(self.r["formula"]), 4)


if __name__ == "__main__":
    unittest.main()
