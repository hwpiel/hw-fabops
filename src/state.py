"""공유 상태 정의 — LangGraph StateGraph 전 노드가 읽고 쓴다."""
from __future__ import annotations

from typing import TypedDict


class OpsState(TypedDict, total=False):
    query: str                 # 엔지니어 자연어 질의
    plan: list[str]            # supervisor 처리 계획(설명용)
    retrieved_docs: list[dict] # retriever: RAG 검색 결과 [{text, metadata, score}]
    kg_paths: list[str]        # retriever: 지식그래프 인과 경로 (하이브리드 검색의 Graph 축)
    sql_results: dict          # data_analyst: 조회·집계 결과
    root_cause: str            # root_cause: 원인 가설
    cost_impact: dict          # cost_impact: 원가·ROI 정량화
    report: str                # report_writer: 경영 보고서 초안
    critiques: list[str]       # validator: 다면 검증 지적
    validation: dict           # validator: 렌즈별 통과 여부 {렌즈명: bool}
    revision_count: int        # 순환 재작업 횟수(무한루프 방지)
    actions: list[dict]        # action_planner: 조치 초안 (작업오더·알람변경, 발행 시뮬레이션)
    next: str                  # 다음 라우팅 대상 노드명 or "END"


WORKERS = ["retriever", "data_analyst", "root_cause", "cost_impact", "report_writer"]
MAX_REVISIONS = 2
