"""지식그래프 경로 탐색 테스트 — 하이브리드 검색의 Graph 축이 인과 사슬을 반환하는지."""
import unittest

from src.kg import extract_paths, find_seed_entities


class TestKnowledgeGraph(unittest.TestCase):
    QUERY = "FAB-A RTP 설비 최근 2주 수율 하락 원인과 재무 영향, 개선 우선순위 알려줘"

    def test_seeds_found(self):
        seeds = find_seed_entities(self.QUERY)
        self.assertIn("RTP", seeds)
        self.assertIn("수율", seeds)

    def test_causal_chain_reachable(self):
        paths = extract_paths(self.QUERY)
        self.assertTrue(paths, "경로가 하나도 없음")
        joined = " | ".join(paths)
        self.assertIn("도펀트 과확산", joined)
        self.assertIn("스크랩", joined)

    def test_no_paths_for_unrelated_query(self):
        self.assertEqual(extract_paths("오늘 점심 뭐 먹지"), [])

    def test_paths_capped(self):
        self.assertLessEqual(len(extract_paths(self.QUERY)), 12)


if __name__ == "__main__":
    unittest.main()
