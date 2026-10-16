"""LangGraph StateGraph 조립.

구조:
    START → supervisor → (retriever|data_analyst|root_cause|cost_impact|report_writer)
    워커 → supervisor (복귀, 다음 빈 칸 채움)
    report_writer → validator
    validator → report_writer(재작업) | END   ← 자가개선 순환 루프
"""
from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .nodes.action_planner import action_planner
from .nodes.cost_impact import cost_impact
from .nodes.data_analyst import data_analyst
from .nodes.report_writer import report_writer
from .nodes.retriever import retriever
from .nodes.root_cause import root_cause
from .nodes.supervisor import supervisor
from .nodes.validator import validator
from .state import OpsState


def _route_supervisor(state: OpsState) -> str:
    return state["next"]


def _route_validator(state: OpsState) -> str:
    return "report_writer" if state.get("next") == "report_writer" else "action_planner"


def build_graph(with_memory: bool = False):
    """with_memory=True 면 InMemorySaver checkpointer 를 붙인다.
    thread_id 별로 상태가 보존되어 세션 내 재실행·이어보기가 가능하다."""
    g = StateGraph(OpsState)

    g.add_node("supervisor", supervisor)
    g.add_node("retriever", retriever)
    g.add_node("data_analyst", data_analyst)
    g.add_node("root_cause", root_cause)
    g.add_node("cost_impact", cost_impact)
    g.add_node("report_writer", report_writer)
    g.add_node("validator", validator)
    g.add_node("action_planner", action_planner)

    g.add_edge(START, "supervisor")
    g.add_conditional_edges(
        "supervisor",
        _route_supervisor,
        ["retriever", "data_analyst", "root_cause", "cost_impact", "report_writer"],
    )
    for worker in ["retriever", "data_analyst", "root_cause", "cost_impact"]:
        g.add_edge(worker, "supervisor")
    g.add_edge("report_writer", "validator")
    g.add_conditional_edges("validator", _route_validator, ["report_writer", "action_planner"])
    g.add_edge("action_planner", END)

    if with_memory:
        from langgraph.checkpoint.memory import InMemorySaver

        return g.compile(checkpointer=InMemorySaver())
    return g.compile()


if __name__ == "__main__":
    import sys

    app = build_graph()
    q = sys.argv[1] if len(sys.argv) > 1 else "FAB-A RTP 설비 최근 2주 수율 하락 원인과 재무 영향, 개선 우선순위 알려줘"
    final = app.invoke({"query": q, "revision_count": 0}, {"recursion_limit": 40})
    print("\n===== 계획 =====\n", "\n".join(final.get("plan", [])))
    print("\n===== 원인 =====\n", final.get("root_cause", ""))
    print("\n===== 원가 임팩트 =====\n", final.get("cost_impact", {}))
    print("\n===== 보고서 =====\n", final.get("report", ""))
    print("\n===== 검증 지적 =====\n", "\n".join(final.get("critiques", []) or ["(없음)"]))
    print("\n===== 조치 초안 =====\n", final.get("actions", []))
