"""경량 지식그래프(KG) — 온톨로지 기반 인과 경로 탐색.

벡터 검색(유사도)이 놓치는 다단계 관계(설비→파라미터→메커니즘→계측→원가)를
사람이 정의한 온톨로지(data/ontology.json)에서 경로로 추출해 검색을 보강한다
(하이브리드 검색 = Vector + Graph). 순수 Python 구현 — 그래프 DB 없이 동작하며,
Neo4j·LLM 자동 KG 구축은 로드맵으로 남긴다.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

ONTOLOGY_PATH = Path(__file__).resolve().parents[1] / "data" / "ontology.json"

MAX_DEPTH = 4
MAX_PATHS = 12


@lru_cache(maxsize=1)
def load_ontology() -> dict:
    return json.loads(ONTOLOGY_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _adjacency() -> dict[str, list[tuple[str, str]]]:
    """양방향 인접 리스트. (관계라벨, 이웃) — 역방향은 라벨에 ← 표기."""
    adj: dict[str, list[tuple[str, str]]] = {}
    for s, rel, o in load_ontology()["relations"]:
        adj.setdefault(s, []).append((rel, o))
        adj.setdefault(o, []).append((f"{rel}←", s))
    return adj


def find_seed_entities(query: str) -> list[str]:
    """질의 문장에 등장하는 엔티티(id 또는 라벨 부분일치)를 시드로 수집."""
    q = query.lower()
    seeds = []
    for eid, meta in load_ontology()["entities"].items():
        if eid.lower() in q or meta.get("label", "").lower() in q:
            seeds.append(eid)
    # 구체 엔티티(설비 등)가 있으면 일반 엔티티(공정단계)에 흡수되는 중복 제거는
    # 하지 않는다 — 경로 다양성이 근거 폭을 넓힌다.
    return seeds


def _walk(start: str) -> list[list[str]]:
    """start 에서 정방향 우선 DFS 로 경로 수집(사이클·즉시 역행 방지)."""
    paths: list[list[str]] = []

    def dfs(node: str, path_nodes: list[str], path_repr: list[str], depth: int):
        if len(paths) >= MAX_PATHS:
            return
        if depth >= MAX_DEPTH:
            if len(path_repr) > 1:
                paths.append(path_repr[:])
            return
        extended = False
        for rel, nxt in _adjacency().get(node, []):
            if nxt in path_nodes:
                continue
            extended = True
            dfs(nxt, path_nodes + [nxt], path_repr + [f"--{rel}-->", nxt], depth + 1)
        if not extended and len(path_repr) > 1:
            paths.append(path_repr[:])

    dfs(start, [start], [start], 0)
    return paths


def extract_paths(query: str) -> list[str]:
    """질의와 연관된 인과 경로를 사람이 읽을 수 있는 문자열로 반환."""
    seen: set[str] = set()
    out: list[str] = []
    for seed in find_seed_entities(query):
        for path in _walk(seed):
            s = " ".join(path)
            if s not in seen:
                seen.add(s)
                out.append(s)
            if len(out) >= MAX_PATHS:
                return out
    return out
