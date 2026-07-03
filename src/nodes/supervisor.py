"""supervisor — 상태 완성도를 보고 다음 워커를 결정하는 라우터.

첫 진입 시 LLM 으로 처리 계획(plan)을 한 번 세워 설명 가능성을 확보하고,
이후에는 State 의 빈 칸을 채우는 순서로 결정론적 라우팅한다(안정성).
"""
from __future__ import annotations

from ..llm import get_chat
from ..state import OpsState
from ..util import text_of

_PLAN_PROMPT = """너는 반도체 Diffusion 공정 운영 분석 오케스트레이터다.
아래 엔지니어 질의를 해결하기 위한 처리 계획을 3~5개의 짧은 한국어 단계로만 제시하라.
각 줄은 '-' 로 시작. 사용할 수 있는 전문 에이전트: 지식검색(RAG), 데이터분석(SQL),
원인규명, 원가임팩트, 보고서작성, 검증.

질의: {query}"""


def supervisor(state: OpsState) -> dict:
    updates: dict = {}

    if not state.get("plan"):
        resp = get_chat().invoke(_PLAN_PROMPT.format(query=state["query"]))
        plan = [ln.strip("- ").strip() for ln in text_of(resp).splitlines() if ln.strip().startswith("-")]
        updates["plan"] = plan or ["지식검색 → 데이터분석 → 원인규명 → 원가임팩트 → 보고서 → 검증"]

    if not state.get("retrieved_docs"):
        nxt = "retriever"
    elif not state.get("sql_results"):
        nxt = "data_analyst"
    elif not state.get("root_cause"):
        nxt = "root_cause"
    elif not state.get("cost_impact"):
        nxt = "cost_impact"
    else:
        nxt = "report_writer"

    updates["next"] = nxt
    return updates
