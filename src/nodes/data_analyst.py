"""data_analyst — 질의를 SQL 로 변환해 MES/FDC(SQLite)를 조회·집계하는 노드.

Legacy System 연계를 시뮬레이션한다. LLM 이 스키마를 보고 SELECT 를 생성하고,
읽기 전용 툴로 실행한 뒤 결과를 상태에 담는다.
"""
from __future__ import annotations

from ..llm import get_chat
from ..state import OpsState
from ..tools import SCHEMA_DOC, run_sql
from ..util import extract_json, text_of

_SQL_PROMPT = """{schema}

엔지니어 질의: {query}

위 질의에 답하는 데 필요한 SELECT 쿼리를 1~3개 만들어라.
수율 이슈라면 lot_yield 의 일별 추이(대조 설비 포함)와 metrology 계측값도 함께 조회하라 —
근거 없는 주장은 검증 단계에서 기각된다.
설명 없이 JSON 배열(문자열 쿼리들)로만 출력하라. 예: ["SELECT ...", "SELECT ..."]"""


def data_analyst(state: OpsState) -> dict:
    resp = get_chat().invoke(_SQL_PROMPT.format(schema=SCHEMA_DOC, query=state["query"]))
    try:
        queries = extract_json(text_of(resp))
        if isinstance(queries, str):
            queries = [queries]
    except Exception:
        queries = []

    results: dict = {}
    for q in queries[:3]:
        try:
            rows = run_sql(q)
            results[q] = rows[:50]
        except Exception as e:
            results[q] = {"error": str(e)}

    if not results:
        results["_note"] = "생성된 쿼리 없음 — 질의를 데이터로 답할 수 없었음"
    return {"sql_results": results}
