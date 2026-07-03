"""cost_impact — 차별화 축1. 원인 규명 '다음'을 담당한다.

산술은 결정론적 모델(src/cost_model.py, symbolic)이 계산하고, 이 노드의 LLM
(neural)은 그 숫자를 바꾸지 않은 채 개선안 도출·해석만 한다. 계산 근거가
상태에 그대로 남아 validator 의 수치정확성 렌즈가 보고서 숫자와 대조한다.

SAP 원가 컨설팅 자산을 에이전트로 이식한 노드.
"""
from __future__ import annotations

import json

from ..cost_model import compute_loss
from ..llm import get_chat
from ..state import OpsState
from ..util import extract_json, text_of

_PROMPT = """너는 제조원가 분석가다. 아래 결정론적으로 계산된 손실액과 원인 가설을 근거로
개선안 2~3개를 도출하라. 계산된 숫자는 절대 바꾸지 말고 그대로 인용한다.
JSON 배열로만 출력한다(설명 금지).

[
  {{"action": "개선안", "est_cost_krw": 정수, "est_benefit_krw": 정수, "roi_note": "근거 한 줄"}}
]

est_benefit_krw 는 월 환산 손실액({monthly} KRW) 중 회복 가능 비율로 추정하고,
roi_note 에 그 가정을 명시하라.

[원인 가설]
{root_cause}

[계산된 손실(변경 금지)]
{computed}"""


def cost_impact(state: OpsState) -> dict:
    computed = compute_loss()
    if "loss_krw" not in computed:
        return {"cost_impact": computed}

    resp = get_chat().invoke(
        _PROMPT.format(
            monthly=computed["monthly_projection_krw"],
            root_cause=state.get("root_cause", ""),
            computed=json.dumps(computed, ensure_ascii=False),
        )
    )
    try:
        options = extract_json(text_of(resp))
        if not isinstance(options, list):
            options = [options]
    except Exception:
        options = [
            {
                "action": "개선안 파싱 실패 — computed 손실액 기준 수동 검토",
                "est_cost_krw": 0,
                "est_benefit_krw": 0,
                "roi_note": "-",
            }
        ]

    return {"cost_impact": {**computed, "improvement_options": options[:3]}}
