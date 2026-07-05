"""report_writer — 기술 이슈를 경영 언어로 구조화한 보고서 초안 생성 노드.

validator 의 지적(critiques)이 있으면 그것을 반영해 재작성한다(순환 루프의 개선 단계).
"""
from __future__ import annotations

import json
import re

from ..llm import get_chat
from ..state import OpsState
from ..util import text_of


def _sanitize(md: str) -> str:
    """LLM 폭주 반복 방어 — 표 구분선 등에서 '-'·':'·'=' 가 수십만 자 반복되며
    출력 토큰을 소진해 보고서가 잘리는 사례가 실측됨. 긴 반복열을 압축한다."""
    md = md.replace("**", "")  # 강조 마크업 금지 원칙 — LLM 이 섞어 내보내는 볼드 제거
    md = re.sub(r"-{4,}", "---", md)
    md = re.sub(r"={4,}", "===", md)
    md = re.sub(r":-{3,}", ":---", md)
    return md

_PROMPT = """너는 반도체 제조기술 현장의 이슈를 임원에게 보고하는 컨설턴트다.
아래 근거로 한국어 경영 보고서 초안을 작성하라. 구조를 반드시 지켜라.

## 배경
## 원인 분석
## 재무 영향
(cost_impact 의 손실액과 내역을 표/수치로. 단위 원(KRW), 천단위 콤마)
## 개선 권고 및 우선순위
(개선안별 ROI 비교, 우선순위 근거)
## 다음 단계

강조용 볼드·별표는 쓰지 말고, 제목과 표로 구조화하라.
표의 구분선은 |---|---| 처럼 셀당 대시 3개만 사용하라. 전체 분량은 1,500자 이내.
수치는 [재무 임팩트(JSON)]의 값을 그대로 인용하고 임의로 반올림·재계산하지 마라.
월 환산 손실을 언급할 때는 산식(직접 손실 ÷ 최근 일수 × 30일)을 함께 명시하라.
개선안의 기대효과를 인용할 때는 그 근거 가정(월 손실의 회복 비율 등)을 함께 명시하라.

[질의] {query}
[원인 가설] {root_cause}
[재무 임팩트(JSON)] {cost}
[검증 피드백(있으면 반드시 반영)] {critiques}"""


def report_writer(state: OpsState) -> dict:
    resp = get_chat(temperature=0.3).invoke(
        _PROMPT.format(
            query=state["query"],
            root_cause=state.get("root_cause", ""),
            cost=json.dumps(state.get("cost_impact", {}), ensure_ascii=False, default=str),
            critiques="\n".join(state.get("critiques", [])) or "없음",
        )
    )
    return {"report": _sanitize(text_of(resp).strip())}
