"""action_planner 테스트 — 조치 초안은 감사 대상이므로 생성 규칙이 결정론적이어야 한다."""
import unittest

from src.nodes.action_planner import action_planner


def _state():
    return {
        "cost_impact": {
            "affected_equip": "RTP-01",
            "improvement_options": [
                {"action": "파이로미터 재캘리브레이션", "est_cost_krw": 8000000, "roi_note": "90% 회복"},
                {"action": "FDC 알람 상한 강화", "est_cost_krw": 2000000, "roi_note": "감지 단축"},
            ],
        }
    }


class TestActionPlanner(unittest.TestCase):
    def setUp(self):
        self.actions = action_planner(_state())["actions"]

    def test_work_orders_from_options(self):
        wos = [a for a in self.actions if a["type"] == "work_order"]
        self.assertEqual(len(wos), 2)
        self.assertEqual(wos[0]["priority"], "P1")
        self.assertEqual(wos[0]["target_equip"], "RTP-01")
        self.assertEqual(wos[0]["est_cost_krw"], 8000000)

    def test_alarm_change_from_ontology(self):
        alarms = [a for a in self.actions if a["type"] == "alarm_change_request"]
        self.assertEqual(len(alarms), 1)
        self.assertEqual(alarms[0]["param"], "peak_temp_C")
        self.assertEqual(alarms[0]["current_limit"], 1055.0)
        self.assertEqual(alarms[0]["proposed_limit"], 1053.0)

    def test_all_drafts(self):
        self.assertTrue(all(a["status"] == "draft" for a in self.actions))

    def test_no_actions_without_options(self):
        out = action_planner({"cost_impact": {"affected_equip": "IMP-02"}})
        self.assertEqual([a for a in out["actions"] if a["type"] == "work_order"], [])


if __name__ == "__main__":
    unittest.main()
