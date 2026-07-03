"""run_sql 안전 가드 테스트 — 읽기 전용 보장은 Legacy 연계의 최소 요건이다."""
import unittest

from src.tools import run_sql


class TestSqlGuard(unittest.TestCase):
    def test_select_allowed(self):
        rows = run_sql("SELECT COUNT(*) AS n FROM lot_yield")
        self.assertGreater(rows[0]["n"], 0)

    def test_with_cte_allowed(self):
        rows = run_sql("WITH t AS (SELECT 1 AS x) SELECT * FROM t")
        self.assertEqual(rows, [{"x": 1}])

    def test_write_rejected(self):
        for bad in ["DROP TABLE lot_yield", "DELETE FROM lot_yield", "UPDATE lot_yield SET yield_pct=0"]:
            with self.assertRaises(ValueError):
                run_sql(bad)

    def test_multi_statement_rejected(self):
        with self.assertRaises(ValueError):
            run_sql("SELECT 1; DROP TABLE lot_yield")


if __name__ == "__main__":
    unittest.main()
