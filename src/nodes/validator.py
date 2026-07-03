"""validator — 차별화 축2. LLM-as-judge 로 보고서를 다면 검증하고 순환 여부를 결정한다.

3개 렌즈(근거 정합성·수치 정확성·논리 구조)로 채점. 하나라도 실패하고 재작업
여지가 남으면 report_writer 로 되돌린다(reflexion cycle). 상한 도달 시 종료.

설계 원칙: 판정 파싱에 실패해도 절대 자동 통과시키지 않는다. 1회 재시도 후에도
실패하면 '검증 불능'을 명시하고 종료한다(fail-visible). 검증기가 고장 났을 때
조용히 통과시키는 것은 검증 없는 것보다 나쁘다.
"""
from __future__ import annotations

import json

from ..llm import get_chat
from ..state import MAX_REVISIONS, OpsState
from ..util import extract_json, text_of

_PROMPT = """너는 엄격한 검토자다. 아래 보고서를 3개 렌즈로 검증하라.
각 렌즈 통과 여부와, 실패 시 구체적 지적을 남겨라. JSON 으로만 출력.

렌즈:
1) 근거정합성 — 보고서 주장이 아래 근거(지식/데이터)에 실제로 뒷받침되는가
2) 수치정확성 — 재무 영향의 수치가 원가 근거(computed)와 일치하고 단위·합계가 맞는가
3) 논리구조 — 배경→원인→재무영향→권고 흐름과 권고-원인 연결이 타당한가

출력 스키마:
{{"passed": true/false, "lenses": {{"근거정합성": bool, "수치정확성": bool, "논리구조": bool}},
  "critiques": ["개선지적1", "..."]}}

[보고서]
{report}

[지식 근거]
{docs}

[데이터/원가 근거]
{evidence}"""

_STRICT_SUFFIX = "\n\n주의: 직전 출력이 JSON 파싱에 실패했다. 코드펜스·설명 없이 JSON 객체만 출력하라."


def validator(state: OpsState) -> dict:
    docs = "\n".join(d["text"][:300] for d in state.get("retrieved_docs", []))
    # daily_yield(시계열)는 부피가 커서 핵심 근거(산식·요약수치)를 밀어내므로 제외
    cost_ev = {k: v for k, v in state.get("cost_impact", {}).items() if k != "daily_yield"}
    evidence = json.dumps(
        {"sql": state.get("sql_results", {}), "cost": cost_ev},
        ensure_ascii=False,
        default=str,
    )[:6000]
    prompt = _PROMPT.format(report=state.get("report", ""), docs=docs, evidence=evidence)

    verdict = None
    for attempt in range(2):
        resp = get_chat(temperature=0.0).invoke(prompt + (_STRICT_SUFFIX if attempt else ""))
        try:
            verdict = extract_json(text_of(resp))
            break
        except Exception:
            continue

    if not isinstance(verdict, dict):
        # 검증 불능 — 통과로 위장하지 않고 한계를 명시한 채 조치 단계로 넘어간다
        return {
            "critiques": ["[검증 판정 파싱 2회 실패 — 자동 검증 불능, 수동 검토 필요]"],
            "validation": {},
            "next": "action_planner",
        }

    passed = bool(verdict.get("passed"))
    critiques = verdict.get("critiques", []) or []
    lenses = verdict.get("lenses", {}) or {}
    rev = state.get("revision_count", 0)

    if passed:
        return {"critiques": critiques, "validation": lenses, "next": "action_planner"}
    if rev >= MAX_REVISIONS:
        return {
            "critiques": critiques + [f"[재작업 상한 {MAX_REVISIONS}회 도달 — 한계 명시하고 종료]"],
            "validation": lenses,
            "next": "action_planner",
        }
    return {"critiques": critiques, "validation": lenses, "revision_count": rev + 1, "next": "report_writer"}
