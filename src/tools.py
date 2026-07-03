"""데이터 접근 툴 — SQLite(MES/FDC) SQL 실행, Chroma 벡터 검색.

Legacy System(MES/FDC) 연계를 시뮬레이션한다. 실제 현장에서는 이 자리에
SAP/MES OData 나 사내 DB 커넥터가 들어간다.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DB_PATH = REPO / "data" / "fab.sqlite"
CHROMA_DIR = REPO / "data" / "chroma_db"
CHROMA_COLLECTION = "diffusion_kb"

SCHEMA_DOC = """테이블 스키마 (SQLite):
equipment_log(ts TEXT, equip_id TEXT, param TEXT, value REAL)   -- FDC 센서 로그
lot_yield(lot_id TEXT, equip_id TEXT, process_step TEXT, yield_pct REAL, wafer_count INT, date TEXT)
metrology(lot_id TEXT, param TEXT, value REAL, spec_lo REAL, spec_hi REAL)  -- CD/THK/OL 계측
cost_master(process_step TEXT, wafer_cost REAL, scrap_cost REAL, rework_cost REAL)  -- 원가(KRW)
규칙: 읽기 전용 SELECT 만. 날짜는 'YYYY-MM-DD'. equip_id 예: RTP-01, IMP-02, DEP-03."""


def run_sql(query: str) -> list[dict]:
    """읽기 전용 조회 실행. SELECT / WITH(CTE) 만 허용, 다중 구문 거부."""
    q = query.strip().rstrip(";")
    if ";" in q:
        raise ValueError("다중 구문은 허용되지 않습니다.")
    head = q.lower().lstrip("(")
    if not (head.startswith("select") or head.startswith("with")):
        raise ValueError("SELECT/WITH 쿼리만 허용됩니다.")
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        rows = con.execute(q).fetchall()
        return [dict(r) for r in rows]
    finally:
        con.close()


def get_vectorstore():
    """Chroma 벡터스토어 핸들 반환 (build_index.py 로 사전 인덱싱 필요)."""
    from langchain_chroma import Chroma

    from .llm import get_embeddings

    return Chroma(
        collection_name=CHROMA_COLLECTION,
        embedding_function=get_embeddings(),
        persist_directory=str(CHROMA_DIR),
    )


def search_docs(query: str, k: int = 4) -> list[dict]:
    vs = get_vectorstore()
    hits = vs.similarity_search_with_relevance_scores(query, k=k)
    return [
        {"text": d.page_content, "metadata": d.metadata, "score": round(float(s), 3)}
        for d, s in hits
    ]
