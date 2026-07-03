"""Fab Data Gateway 테스트 — 주입은 결정론적이고, 분석기가 새 시나리오를 인식해야 한다."""
import unittest

from src.cost_model import compute_loss
from src.scenario import inject, reset
from src.tools import run_sql


class TestScenario(unittest.TestCase):
    def tearDown(self):
        reset()  # 매 테스트 후 기준 데이터 복원

    def test_inject_creates_rows_with_contrast(self):
        r = inject("IMP-02", yield_drop_pp=12.0, days=8)
        self.assertEqual(r["process_step"], "Implant")
        self.assertEqual(len(r["injected_dates"]), 8)
        rows = run_sql(
            f"SELECT COUNT(*) AS n FROM lot_yield WHERE equip_id='IMP-02' AND date >= '{r['injected_dates'][0]}'"
        )
        self.assertEqual(rows[0]["n"], 8)

    def test_injected_anomaly_becomes_worst(self):
        inject("IMP-02", yield_drop_pp=12.0, days=8)
        worst = compute_loss()
        self.assertEqual(worst["affected_equip"], "IMP-02")
        self.assertGreater(worst["yield_loss_pp"], 5.0)

    def test_reset_restores_baseline(self):
        inject("IMP-02", yield_drop_pp=12.0, days=8)
        reset()
        worst = compute_loss()
        self.assertEqual(worst["affected_equip"], "RTP-01")

    def test_unknown_equipment_rejected(self):
        with self.assertRaises(ValueError):
            inject("NO-SUCH-EQ", 5.0)


if __name__ == "__main__":
    unittest.main()
