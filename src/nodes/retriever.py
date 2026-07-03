"""retriever — 하이브리드 검색 노드 (Vector + Knowledge Graph).

벡터 유사도 검색(Chroma)으로 문서 근거를, 온톨로지 경로 탐색(kg)으로
다단계 인과 근거를 함께 수집한다. 유사도는 '비슷한 문서'를 찾고,
그래프는 '연결된 원인 사슬'을 찾는다 — 서로 못 보는 것을 보완한다.
"""
from __future__ import annotations

from ..kg import extract_paths
from ..state import OpsState
from ..tools import search_docs


def retriever(state: OpsState) -> dict:
    docs = search_docs(state["query"], k=4)
    paths = extract_paths(state["query"])
    return {"retrieved_docs": docs, "kg_paths": paths}
