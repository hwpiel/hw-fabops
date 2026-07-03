"""Fab Data Gateway — 데모 중 실시간 시나리오 주입.

실제 현장이라면 MES/FDC 인터페이스가 실시간으로 흘려보낼 데이터를, 데모에서는
이 게이트웨이가 대신 생성해 주입한다. "다른 설비 이슈도 보여달라"는 요청에
재시드 없이 즉석 대응하기 위한 장치다.

- 주입은 결정론적: 같은 요청은 같은 데이터를 만든다(테스트 가능)
- 대상 설비의 이상 로트와 함께, 같은 공정의 대조 설비 정상 로트도 같은 날짜에
  넣는다 — 분석기의 대조군 비교·차트가 성립하도록
- reset() 은 시드 스크립트를 재실행해 기준 상태로 복원한다
"""
from __future__ import annotations

import runpy
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from .tools import DB_PATH

SEED_SCRIPT = Path(__file__).resolve().parents[1] / "data" / "seed_db.py"

# 공정별 대표 파라미터와 (정상 기준값, 이상 시 가산치)
PARAM_PRESET = {
    "RTP": ("peak_temp_C", 1050.0, 12.0),
    "Implant": ("dose", 100.0, -4.0),
    "Deposition": ("particle_count", 130.0, 330.0),
}


def inject(equip_id: str, yield_drop_pp: float, days: int = 6) -> dict:
    """equip_id 에 최근 days 일치 이상 신호(수율 하락 + 파라미터 이상)를 주입한다."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        row = con.execute(
            "SELECT process_step, AVG(yield_pct) AS base FROM lot_yield WHERE equip_id=? GROUP BY process_step",
            (equip_id,),
        ).fetchone()
        if not row:
            raise ValueError(f"미등록 설비: {equip_id}")
        process, base_yield = row["process_step"], float(row["base"])

        sib = con.execute(
            "SELECT equip_id, AVG(yield_pct) AS base FROM lot_yield WHERE process_step=? AND equip_id!=? GROUP BY equip_id LIMIT 1",
            (process, equip_id),
        ).fetchone()

        last = con.execute("SELECT MAX(date) AS d FROM lot_yield").fetchone()["d"]
        start = date.fromisoformat(last) + timedelta(days=1)

        seq = con.execute("SELECT COUNT(*) AS n FROM lot_yield").fetchone()["n"]
        param, p_base, p_delta = PARAM_PRESET.get(process, ("param_x", 100.0, 10.0))

        new_dates = []
        for i in range(days):
            d = (start + timedelta(days=i)).isoformat()
            new_dates.append(d)
            seq += 1
            con.execute(
                "INSERT INTO lot_yield VALUES (?,?,?,?,?,?)",
                (f"L{seq:04d}", equip_id, process, round(base_yield - yield_drop_pp + (i % 2) * 0.2, 2), 25, d),
            )
            con.execute(
                "INSERT INTO equipment_log VALUES (?,?,?,?)",
                (f"{d}T02:00", equip_id, param, round(p_base + p_delta + (i % 3) * 0.3, 1)),
            )
            if sib:
                seq += 1
                con.execute(
                    "INSERT INTO lot_yield VALUES (?,?,?,?,?,?)",
                    (f"L{seq:04d}", sib["equip_id"], process, round(float(sib["base"]) + (i % 2) * 0.2, 2), 25, d),
                )
        con.commit()
        return {
            "equip_id": equip_id,
            "process_step": process,
            "yield_drop_pp": yield_drop_pp,
            "param": param,
            "injected_dates": new_dates,
            "contrast_equip": sib["equip_id"] if sib else None,
        }
    finally:
        con.close()


def reset() -> dict:
    """시드 스크립트 재실행 — 기준 데이터로 복원."""
    runpy.run_path(str(SEED_SCRIPT), run_name="__main__")
    return {"reset": True}
