"""MES/FDC 시뮬레이션 SQLite 생성·시드.

데모 신호: RTP-01 설비가 최근 1주 peak_temp 상승과 함께 수율이 96%대 → 88%대로 하락.
실행:  python data/seed_db.py
"""
from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

DB = Path(__file__).resolve().parent / "fab.sqlite"

SCHEMA = """
DROP TABLE IF EXISTS equipment_log;
DROP TABLE IF EXISTS lot_yield;
DROP TABLE IF EXISTS metrology;
DROP TABLE IF EXISTS cost_master;
CREATE TABLE equipment_log (ts TEXT, equip_id TEXT, param TEXT, value REAL);
CREATE TABLE lot_yield (lot_id TEXT, equip_id TEXT, process_step TEXT, yield_pct REAL, wafer_count INT, date TEXT);
CREATE TABLE metrology (lot_id TEXT, param TEXT, value REAL, spec_lo REAL, spec_hi REAL);
CREATE TABLE cost_master (process_step TEXT, wafer_cost REAL, scrap_cost REAL, rework_cost REAL);
"""

START = date(2026, 6, 16)  # 2주 전
DAYS = 15


def build():
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)

    eq_rows, yield_rows, met_rows = [], [], []
    lot_seq = 0
    for i in range(DAYS):
        d = START + timedelta(days=i)
        ds = d.isoformat()
        recent = i >= 9  # 최근 6일에 이상 신호

        # RTP-01: 최근 peak_temp 상승, 수율 하락 (문제 설비)
        peak = 1050.0 + (12.0 if recent else 0.0) + (i % 3) * 0.4
        eq_rows.append((f"{ds}T02:00", "RTP-01", "peak_temp_C", round(peak, 1)))
        eq_rows.append((f"{ds}T02:00", "RTP-01", "ramp_rate_Cps", round(75.0 + (8.0 if recent else 0.0), 1)))
        y_rtp = 88.0 + (i % 3) * 0.5 if recent else 96.2 + (i % 3) * 0.3
        lot_seq += 1
        lot = f"L{lot_seq:04d}"
        yield_rows.append((lot, "RTP-01", "RTP", round(y_rtp, 2), 25, ds))
        met_rows.append((lot, "sheet_res_ohm", round(210.0 + (18.0 if recent else 2.0), 1), 195.0, 215.0))

        # RTP-02: 정상 대조군
        lot_seq += 1
        lot2 = f"L{lot_seq:04d}"
        eq_rows.append((f"{ds}T03:00", "RTP-02", "peak_temp_C", round(1050.0 + (i % 3) * 0.4, 1)))
        yield_rows.append((lot2, "RTP-02", "RTP", round(96.0 + (i % 3) * 0.3, 2), 25, ds))

        # IMP-02(이온주입): 정상
        lot_seq += 1
        yield_rows.append((f"L{lot_seq:04d}", "IMP-02", "Implant", round(97.1 + (i % 2) * 0.2, 2), 25, ds))

        # DEP-03(박막): 2차 시나리오 — 최근 파티클 상승과 함께 경미한 수율 하락
        #   (주 시나리오 RTP-01 보다 작게 유지해 cost_model 의 worst 판정을 흔들지 않는다)
        lot_seq += 1
        y_dep = 94.2 + (i % 2) * 0.2 if recent else 95.8 + (i % 2) * 0.2
        yield_rows.append((f"L{lot_seq:04d}", "DEP-03", "Deposition", round(y_dep, 2), 25, ds))
        particle = 460 + (i % 5) * 15 if recent else 120 + (i % 5) * 10
        eq_rows.append((f"{ds}T04:00", "DEP-03", "particle_count", float(particle)))

    con.executemany("INSERT INTO equipment_log VALUES (?,?,?,?)", eq_rows)
    con.executemany("INSERT INTO lot_yield VALUES (?,?,?,?,?,?)", yield_rows)
    con.executemany("INSERT INTO metrology VALUES (?,?,?,?,?)", met_rows)
    con.executemany(
        "INSERT INTO cost_master VALUES (?,?,?,?)",
        [
            ("RTP", 3_200_000, 2_600_000, 850_000),
            ("Implant", 3_200_000, 2_600_000, 700_000),
            ("Deposition", 3_200_000, 2_600_000, 780_000),
        ],
    )
    con.commit()
    n = con.execute("SELECT COUNT(*) FROM lot_yield").fetchone()[0]
    con.close()
    print(f"seeded {DB}  (lot_yield {n} rows, equipment_log {len(eq_rows)}, metrology {len(met_rows)})")


if __name__ == "__main__":
    build()
