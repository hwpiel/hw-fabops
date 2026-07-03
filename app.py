"""Streamlit 데모 — 질의 입력 → 그래프 실행 → 노드별 중간 결과 + 최종 보고서.

그래프는 한 번만 실행한다. stream 의 노드별 업데이트를 누적해 최종 상태를 만든다
(stream 후 invoke 를 또 하면 파이프라인이 두 번 돌고, 로그와 결과가 서로 다른
실행의 산물이 되는 불일치가 생긴다).
"""
from __future__ import annotations

import streamlit as st

from src.graph import build_graph

st.set_page_config(page_title="Diffusion 공정 운영 멀티에이전트", layout="wide")
st.title("Diffusion 공정 운영 멀티에이전트")
st.caption("RAG + SQL + 결정론적 원가모델 + 자가검증 · LangGraph 순환 멀티에이전트")

EXAMPLES = [
    "M15 RTP 설비 최근 2주 수율 하락 원인과 재무 영향, 개선 우선순위 알려줘",
    "DEP-03 결함 이슈 원인과 원가 영향 분석해줘",
]

NODE_LABEL = {
    "supervisor": "supervisor — 라우팅",
    "retriever": "retriever — 공정 지식 검색(RAG)",
    "data_analyst": "data_analyst — MES/FDC SQL 조회",
    "root_cause": "root_cause — 원인 가설",
    "cost_impact": "cost_impact — 원가 임팩트 정량화",
    "report_writer": "report_writer — 경영 보고서 작성",
    "validator": "validator — 다면 검증",
}

query = st.text_input("엔지니어 질의", EXAMPLES[0])
with st.expander("예시 질의"):
    for e in EXAMPLES:
        st.write("-", e)

if st.button("분석 실행", type="primary"):
    if "graph" not in st.session_state:
        st.session_state.graph = build_graph(with_memory=True)
        st.session_state.thread_id = "st-session"
    app = st.session_state.graph
    config = {"recursion_limit": 40, "configurable": {"thread_id": st.session_state.thread_id}}
    final: dict = {"query": query, "revision_count": 0}
    with st.status("에이전트 그래프 실행 중...", expanded=True) as status:
        for chunk in app.stream({"query": query, "revision_count": 0}, config):
            for node, update in chunk.items():
                final.update(update or {})
                st.write("●", NODE_LABEL.get(node, node))
        status.update(label="완료", state="complete")

    left, right = st.columns([1, 1])
    with left:
        st.subheader("처리 계획")
        for p in final.get("plan", []):
            st.write("-", p)
        st.subheader("지식그래프 인과 경로")
        for kp in final.get("kg_paths", []) or ["(경로 없음)"]:
            st.code(kp, language=None)
        st.subheader("원인 가설")
        st.write(final.get("root_cause", ""))
        st.subheader("원가 임팩트")
        st.json(final.get("cost_impact", {}))
        st.subheader("검증 지적")
        st.write("\n".join(final.get("critiques", []) or ["(없음 — 통과)"]))
    with right:
        st.subheader("경영 보고서")
        st.markdown(final.get("report", ""))
