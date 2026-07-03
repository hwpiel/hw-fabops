"""action_planner — 분석의 끝을 '실행'으로 잇는 노드 (분석·실행 End-to-End).

개선안을 Legacy 시스템으로 되쓸 조치 초안으로 변환한다:
  - work_order          : MES 작업 오더 초안 (개선안 → 우선순위 부여)
  - alarm_change_request: FDC 알람 관리 상한 변경 요청 초안 (온톨로지의
                          관리파라미터 + SOP 근거 기준값 연동)

LLM 을 쓰지 않는 결정론 노드다. 조치는 감사(audit) 대상 산출물이므로 생성
규칙이 코드로 고정되어야 하고 단위테스트로 검증한다. 발행은 시뮬레이션 —
실연동 시 이 노드가 MES/FDC 커넥터를 호출하는 자리다.
"""
from __future__ import annotations

from ..kg import load_ontology
from ..state import OpsState

# SOP 문서 근거의 관리 기준값 (sop_rtp.md: 관리상한 1055℃ / 과거 이슈 조치: 1053℃ 강화,
#  fdc_alarm_guide.md: 파티클 급증 시 상한 강화)
PARAM_LIMITS = {
    "peak_temp_C": {"current": 1055.0, "proposed": 1053.0, "unit": "℃"},
    "particle_count": {"current": 400.0, "proposed": 350.0, "unit": "ea"},
}


def _managed_params(equip: str) -> list[str]:
    return [
        o for s, rel, o in load_ontology()["relations"]
        if s == equip and rel == "관리파라미터"
    ]


def action_planner(state: OpsState) -> dict:
    c = state.get("cost_impact", {})
    equip = c.get("affected_equip", "")
    actions: list[dict] = []

    for i, o in enumerate(c.get("improvement_options", [])[:3]):
        actions.append({
            "type": "work_order",
            "title": o.get("action", ""),
            "target_equip": equip,
            "priority": f"P{i + 1}",
            "est_cost_krw": int(o.get("est_cost_krw", 0) or 0),
            "rationale": o.get("roi_note", ""),
            "status": "draft",
        })

    for p in _managed_params(equip):
        if p in PARAM_LIMITS:
            lim = PARAM_LIMITS[p]
            actions.append({
                "type": "alarm_change_request",
                "target_equip": equip,
                "param": p,
                "current_limit": lim["current"],
                "proposed_limit": lim["proposed"],
                "unit": lim["unit"],
                "rationale": "이상 재발 조기 감지를 위한 관리 상한 강화 (SOP·과거 이슈 조치 기준)",
                "status": "draft",
            })

    return {"actions": actions}
