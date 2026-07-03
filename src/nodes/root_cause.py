"""root_cause — 지식(RAG)과 데이터(SQL)를 종합해 원인 가설을 도출하는 노드."""
from __future__ import annotations

import json

from ..llm import get_chat
from ..state import OpsState
from ..util import text_of

_PROMPT = """너는 반도체 Diffusion 공정 엔지니어다. 아래 근거를 종합해 이슈의
가장 유력한 원인 가설을 한국어로 제시하라. 데이터 수치와 지식 문서를 함께 인용하고,
지식그래프 인과 경로가 있으면 그 사슬을 따라 원인→결과를 설명하라.
확신 정도(높음/중간/낮음)를 밝혀라. 3~6문장.

[질의]
{query}

[지식그래프 인과 경로 (온톨로지 기반)]
{kg}

[공정 지식 검색결과]
{docs}

[설비/계측 데이터]
{sql}"""


def root_cause(state: OpsState) -> dict:
    docs = "\n\n".join(
        f"- ({d['metadata'].get('process','?')}/{d['metadata'].get('equipment','?')}) {d['text']}"
        for d in state.get("retrieved_docs", [])
    )
    kg = "\n".join(state.get("kg_paths", [])) or "(경로 없음)"
    sql = json.dumps(state.get("sql_results", {}), ensure_ascii=False, default=str)[:3000]
    resp = get_chat().invoke(_PROMPT.format(query=state["query"], kg=kg, docs=docs, sql=sql))
    return {"root_cause": text_of(resp).strip()}
