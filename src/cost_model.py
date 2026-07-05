"""결정론적 원가 손실 모델 (symbolic 계산부).

원가 산술은 LLM 에 맡기지 않는다 — LLM 은 곱셈을 틀린다. 이 모듈은 순수
Python 으로 손실액을 계산하고, LLM(neural 해석부)은 이 숫자를 바꾸지 않은 채
해석·개선안 도출만 담당한다. validator 의 수치정확성 렌즈가 보고서 숫자를
이 모듈의 출력과 대조한다. LLM 의존이 없어 단독 단위테스트가 가능하다.
"""
from __future__ import annotations

from statistics import mean, pstdev

from .tools import run_sql


def compute_loss(target_equip: str | None = None) -> dict:
    """lot_yield 전 기간을 전반/후반으로 나눠 수율 하락 설비의 손실액을 결정론 계산한다.

    target_equip 이 주어지고 해당 설비에 유효한 하락이 있으면 그 설비를 분석한다
    (질의가 특정 설비를 지목한 경우 — 전역 최악 설비로 대답하는 불일치 방지).
    없거나 하락이 없으면 전역 최악 설비로 폴백한다."""
    rows = run_sql(
        "SELECT equip_id, process_step, date, yield_pct, wafer_count FROM lot_yield ORDER BY date"
    )
    if not rows:
        return {"error": "lot_yield 데이터 없음"}

    dates = sorted({r["date"] for r in rows})
    mid = dates[len(dates) // 2]

    by_equip: dict[str, dict] = {}
    for r in rows:
        e = by_equip.setdefault(
            r["equip_id"],
            {"process_step": r["process_step"], "base": [], "recent": [], "recent_wafers": 0},
        )
        if r["date"] < mid:
            e["base"].append(r["yield_pct"])
        else:
            e["recent"].append(r["yield_pct"])
            e["recent_wafers"] += r["wafer_count"]

    worst_id, worst = None, None
    for eid, e in by_equip.items():
        if not e["base"] or not e["recent"]:
            continue
        e["baseline_yield"] = round(mean(e["base"]), 2)
        e["recent_yield"] = round(mean(e["recent"]), 2)
        e["delta_pp"] = round(e["baseline_yield"] - e["recent_yield"], 2)
        if worst is None or e["delta_pp"] > worst["delta_pp"]:
            worst_id, worst = eid, e

    # 질의가 지목한 설비에 유효한 하락이 있으면 그 설비를 우선한다
    if target_equip and target_equip in by_equip:
        t = by_equip[target_equip]
        if t.get("delta_pp", 0) > 0:
            worst_id, worst = target_equip, t

    if worst is None or worst["delta_pp"] <= 0:
        return {
            "note": "유의미한 수율 하락 설비 없음",
            "by_equip": {k: v.get("delta_pp") for k, v in by_equip.items()},
        }

    cost_rows = run_sql(
        f"SELECT wafer_cost, scrap_cost, rework_cost FROM cost_master WHERE process_step = '{worst['process_step']}'"
    )
    cost = cost_rows[0] if cost_rows else {"wafer_cost": 0, "scrap_cost": 0, "rework_cost": 0}

    lost_wafers = round(worst["recent_wafers"] * worst["delta_pp"] / 100)
    scrap_loss = int(lost_wafers * cost["scrap_cost"])
    n_recent_days = len([d for d in dates if d >= mid])
    monthly_projection = int(scrap_loss / max(n_recent_days, 1) * 30)

    # 통계적 유의성 게이트 (SPC 3σ 준용) — 평균 차이가 기준기간 정상 변동(σ) 대비
    # 3배를 넘을 때만 '이상'으로 판정한다. 오탐(정상 변동을 이상으로 오인)은
    # 불필요한 PM·라인 정지로 이어지므로, 판정 근거를 수치로 남긴다.
    base_sigma = round(pstdev(worst["base"]), 3) if len(worst["base"]) > 1 else 0.0
    sigma_multiple = round(worst["delta_pp"] / base_sigma, 1) if base_sigma > 0 else None
    significance = {
        "baseline_sigma_pp": base_sigma,
        "sigma_multiple": sigma_multiple,
        "significant": bool(sigma_multiple is not None and sigma_multiple >= 3.0),
        "rule": "수율 하락폭이 기준기간 표준편차(σ)의 3배 이상일 때 이상 판정 (SPC 3σ 준용)",
    }

    # 근거 데이터: 대조 설비(동일 공정, 변동 최소) + 일별 수율 시계열 — 화면의 트렌드 차트가 소비
    contrast_id = None
    for eid, e in by_equip.items():
        if eid == worst_id or e.get("process_step") != worst["process_step"] or "delta_pp" not in e:
            continue
        if contrast_id is None or abs(e["delta_pp"]) < abs(by_equip[contrast_id]["delta_pp"]):
            contrast_id = eid
    daily: dict[str, dict[str, list]] = {}
    for r in rows:
        if r["equip_id"] in (worst_id, contrast_id):
            daily.setdefault(r["equip_id"], {}).setdefault(r["date"], []).append(r["yield_pct"])
    daily_yield = {
        eid: [{"date": d, "yield_pct": round(mean(v), 2)} for d, v in sorted(dd.items())]
        for eid, dd in daily.items()
    }

    sig_line = (
        f"이상 판정: 하락 {worst['delta_pp']}%p = 기준기간 σ({base_sigma}%p)의 {sigma_multiple}배 ≥ 3σ → 통계적으로 유의"
        if significance["significant"]
        else f"이상 판정 보류: 하락 {worst['delta_pp']}%p = 기준기간 σ({base_sigma}%p)의 {sigma_multiple}배 < 3σ — 정상 변동 범위 가능"
    )
    return {
        "contrast_equip": contrast_id,
        "daily_yield": daily_yield,
        "anomaly_from": mid,
        "significance": significance,
        "formula": [
            sig_line,
            f"손실 웨이퍼 {lost_wafers}장 = 최근 투입 {worst['recent_wafers']}장 × 수율하락 {worst['delta_pp']}%p",
            f"손실액 {scrap_loss:,}원 = {lost_wafers}장 × 스크랩원가 {int(cost['scrap_cost']):,}원/장",
            f"월 환산 {monthly_projection:,}원 = {scrap_loss:,}원 ÷ 최근 {n_recent_days}일 × 30일",
        ],
        "affected_equip": worst_id,
        "affected_process": worst["process_step"],
        "baseline_yield_pct": worst["baseline_yield"],
        "recent_yield_pct": worst["recent_yield"],
        "yield_loss_pp": worst["delta_pp"],
        "recent_wafers": worst["recent_wafers"],
        "lost_wafers": lost_wafers,
        "scrap_cost_per_wafer_krw": int(cost["scrap_cost"]),
        "loss_krw": scrap_loss,
        "monthly_projection_krw": monthly_projection,
        "assumptions": [
            f"기준수율 = 전반기({dates[0]}~{mid} 이전) 평균, 최근수율 = 후반기 평균",
            "손실 웨이퍼 = 최근 투입량 × 수율하락(pp), 전량 스크랩 가정(보수적)",
            "재작업 회복·기회손실 미포함 — 실제 손실은 이보다 클 수 있음",
            "월 환산 = 최근 기간 일평균 × 30일",
        ],
    }
