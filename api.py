"""FastAPI 서버 — 콘솔 UI 와 LangGraph 파이프라인을 잇는다.

POST /api/analyze : 질의를 그래프로 완주시키고, 최종 상태를 UI 데이터 계약
                    (ui/index.html 의 MOCK 과 동일 셰이프)으로 매핑해 반환
GET  /            : ui/ 정적 서빙 (단일 페이지 콘솔)

실행:  uvicorn api:app --port 8796   (또는 python api.py)
"""
from __future__ import annotations

import re
from pathlib import Path

import json
import sqlite3
import time
import uuid
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src import scenario
from src.graph import build_graph
from src.llm import CHAT_MODEL
from src.nodes.action_planner import PARAM_LIMITS, _managed_params
from src.tools import DB_PATH, run_sql

ROOT = Path(__file__).resolve().parent


def _bootstrap():
    """클라우드 배포 대응 — 부팅 시 데이터가 없으면 스스로 만든다.

    fab.sqlite 없음 → 시드 생성. chroma_db 없음 → RAG 인덱스 구축(키 필요,
    실패해도 서버는 뜬다 — UI 가 목데이터로 폴백하므로 화면 데모는 유지된다).
    """
    import runpy

    if not (ROOT / "data" / "fab.sqlite").exists():
        runpy.run_path(str(ROOT / "data" / "seed_db.py"), run_name="__main__")
    if not (ROOT / "data" / "chroma_db").exists():
        try:
            runpy.run_path(str(ROOT / "data" / "build_index.py"), run_name="__main__")
        except Exception as e:
            print(f"[bootstrap] RAG 인덱스 구축 실패(키 미설정?): {e} — 목데이터 모드로 서빙")

    # 감사 이력 — 모든 분석 실행을 서버에 남긴다 (조회는 Raw 데이터 브라우저에서)
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """CREATE TABLE IF NOT EXISTS audit_runs (
            run_id TEXT, ts TEXT, query TEXT, affected_equip TEXT,
            loss_krw INTEGER, validation TEXT, revisions INTEGER,
            duration_s REAL, model TEXT)"""
    )
    con.commit()
    con.close()


_bootstrap()

app = FastAPI(title="hw-fabops API")
GRAPH = build_graph()


class AnalyzeIn(BaseModel):
    query: str


class ScenarioIn(BaseModel):
    equip_id: str
    yield_drop_pp: float = 6.0
    days: int = 6


def _confidence(root_cause: str) -> str:
    m = re.search(r"확신\s*(?:정도|도)?\s*[::]?\s*(높음|중간|낮음)", root_cause or "")
    return m.group(1) if m else "중간"


def _evidence(state: dict) -> dict:
    """그래프 상태의 근거(sql_results·retrieved_docs)와 FDC 트렌드를 UI 계약으로 매핑."""
    sql = [
        {
            "query": q,
            "row_count": len(rows) if isinstance(rows, list) else 0,
            "rows": rows[:8] if isinstance(rows, list) else [{"error": str(rows)}],
        }
        for q, rows in (state.get("sql_results") or {}).items()
        if not q.startswith("_")
    ]
    docs = [
        {
            "source": d.get("metadata", {}).get("source", "?"),
            "doctype": d.get("metadata", {}).get("doctype", "?"),
            "score": float(d.get("score", 0.0)),
            "excerpt": (d.get("text", "") or "")[:150].replace("\n", " "),
        }
        for d in (state.get("retrieved_docs") or [])
    ]

    param_trend = {}
    equip = (state.get("cost_impact") or {}).get("affected_equip")
    if equip:
        for p in _managed_params(equip):
            try:
                rows = run_sql(
                    f"SELECT ts, value FROM equipment_log WHERE equip_id='{equip}' AND param='{p}' ORDER BY ts"
                )
            except Exception:
                rows = []
            if rows:
                param_trend = {
                    "param": p,
                    "equip": equip,
                    "limit": PARAM_LIMITS.get(p, {}).get("current"),
                    "points": [{"date": r["ts"][5:10], "value": r["value"]} for r in rows],
                }
                break

    return {"sql": sql, "docs": docs, "param_trend": param_trend}


@app.post("/api/analyze")
def analyze(body: AnalyzeIn):
    t0 = time.time()
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    state = GRAPH.invoke(
        {"query": body.query, "revision_count": 0}, {"recursion_limit": 40}
    )
    duration = round(time.time() - t0, 1)

    c = state.get("cost_impact") or {}
    v = state.get("validation") or {}
    con = sqlite3.connect(DB_PATH)
    con.execute(
        "INSERT INTO audit_runs VALUES (?,?,?,?,?,?,?,?,?)",
        (
            run_id,
            datetime.now().isoformat(timespec="seconds"),
            body.query,
            c.get("affected_equip"),
            c.get("loss_krw"),
            f"{sum(1 for x in v.values() if x)}/{len(v)}" if v else "n/a",
            state.get("revision_count", 0),
            duration,
            CHAT_MODEL,
        ),
    )
    con.commit()
    con.close()

    return {
        "query": body.query,
        "run_id": run_id,
        "model": CHAT_MODEL,
        "duration_s": duration,
        "plan": state.get("plan", []),
        "root_cause": state.get("root_cause", ""),
        "confidence": _confidence(state.get("root_cause", "")),
        "kg_paths": state.get("kg_paths", []),
        "cost_impact": state.get("cost_impact", {}),
        "report": state.get("report", ""),
        "critiques": state.get("critiques", []),
        "validation": state.get("validation", {}),
        "revision": state.get("revision_count", 0) + 1,
        "actions": state.get("actions", []),
        "evidence": _evidence(state),
    }


# ── 메타 조회 (ERP형 콘솔의 정의서·데이터 브라우저·연계 현황용, 전부 읽기전용) ──

_TABLES = {  # 화이트리스트: 테이블명 → 정렬 컬럼(최근 우선)
    "lot_yield": "date",
    "equipment_log": "ts",
    "metrology": None,
    "cost_master": None,
    "audit_runs": "ts",
}

_SOURCES = [
    ("MES 로트 이력", "lot_yield", "date", "제조실행(MES)"),
    ("FDC 설비 센서", "equipment_log", "ts", "설비 센서(FDC)"),
    ("계측 데이터", "metrology", None, "계측(YMS)"),
    ("원가 기준정보", "cost_master", None, "원가(SAP CO)"),
]


@app.get("/api/meta/status")
def meta_status():
    out = []
    for name, tbl, tscol, kind in _SOURCES:
        n = run_sql(f"SELECT COUNT(*) AS n FROM {tbl}")[0]["n"]
        last = run_sql(f"SELECT MAX({tscol}) AS m FROM {tbl}")[0]["m"] if tscol else None
        out.append({"name": name, "table": tbl, "kind": kind, "rows": n, "last": last, "mode": "simulation"})
    return out


@app.get("/api/meta/table/{name}")
def meta_table(name: str, limit: int = 50):
    if name not in _TABLES:
        raise HTTPException(404, "unknown table")
    limit = max(1, min(int(limit), 200))
    order = _TABLES[name]
    rows = run_sql(
        f"SELECT * FROM {name}" + (f" ORDER BY {order} DESC" if order else "") + f" LIMIT {limit}"
    )
    total = run_sql(f"SELECT COUNT(*) AS n FROM {name}")[0]["n"]
    return {"table": name, "rows": rows, "total": total}


@app.get("/api/meta/ontology")
def meta_ontology():
    return json.loads((ROOT / "data" / "ontology.json").read_text(encoding="utf-8"))


@app.post("/api/scenario")
def scenario_inject(body: ScenarioIn):
    """Fab Data Gateway — 데모 중 새 이상 시나리오를 실시간 주입."""
    try:
        return scenario.inject(body.equip_id, body.yield_drop_pp, body.days)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/scenario/reset")
def scenario_reset():
    """기준 시드 데이터로 복원."""
    return scenario.reset()


app.mount("/", StaticFiles(directory=str(ROOT / "ui"), html=True), name="ui")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8796)
