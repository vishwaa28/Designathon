"""LangGraph definition of the disruption recovery workflow."""
from __future__ import annotations

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from app.agents.approval import approval_node
from app.agents.detection_agent import detection_node, route_after_detection
from app.agents.impact_agent import impact_node
from app.agents.infra_agent import infra_node
from app.agents.notification_agent import notification_node
from app.agents.recovery_agent import recovery_node
from app.agents.state import RecoveryState
from app.agents.tradeoff_agent import tradeoff_node

AGENT_REGISTRY = {
    "detection": {
        "title": "Disruption Detection", "kind": "agent", "icon": "radar",
        "role": "Evaluates weather, asset-health and status feeds against operating thresholds, classifies severity and scopes the disruption window.",
        "inputs": ["Weather feed", "Asset-health stream", "Flight / train status"],
        "outputs": ["Severity", "Scope & window", "Situation report"],
        "tools": ["Threshold rules", "Asset registry", "Language model"],
    },
    "impact_analysis": {
        "title": "Impact Analysis", "kind": "agent", "icon": "network",
        "role": "Propagates delay through aircraft and rake rotations, checks crew duty-time limits and finds missed connections and priority passengers.",
        "inputs": ["Disruption scope", "Schedule", "Crew rosters", "Bookings"],
        "outputs": ["Impacted services", "Crew breaches", "Missed connections", "Priority passengers"],
        "tools": ["Rotation propagation", "Duty-time calculator", "Connection checker", "Language model"],
    },
    "infra_triage": {
        "title": "Infrastructure Triage", "kind": "agent", "icon": "wrench",
        "role": "Ranks probable root causes, dispatches the nearest qualified team, raises the work order and estimates the repair window (P50 / P90).",
        "inputs": ["Asset telemetry", "Fault knowledge base", "Maintenance teams"],
        "outputs": ["Work order", "Repair window", "Parts & safety plan"],
        "tools": ["Fault models", "Team dispatcher", "Parts lookup", "Language model"],
    },
    "recovery_planner": {
        "title": "Recovery Planner", "kind": "agent", "icon": "route",
        "role": "Generates alternative recovery plans (retime, cancel, divert, swap, alternate mode) and re-accommodates passengers against seat inventory and transit rules.",
        "inputs": ["Impact", "Repair window", "Seat inventory", "Reserve crew"],
        "outputs": ["Recovery options", "Constraint checks", "Cost breakdown"],
        "tools": ["Strategy library", "Inventory allocator", "Crew allocator", "Cost model"],
    },
    "tradeoff_analyst": {
        "title": "Trade-off Analyst", "kind": "agent", "icon": "scale",
        "role": "Scores each option on passenger impact, cost, risk and recovery time, computes confidence and explains the trade-offs.",
        "inputs": ["Recovery options", "Controller priorities", "Repair uncertainty"],
        "outputs": ["Scores", "Confidence", "Recommendation rationale"],
        "tools": ["Multi-criteria scoring", "Sensitivity analysis", "Language model"],
    },
    "controller_approval": {
        "title": "Controller Approval", "kind": "human", "icon": "user-check",
        "role": "Pauses the workflow for the duty controller to approve, override, re-plan with new priorities or inject new information.",
        "inputs": ["Ranked options", "Rationale"],
        "outputs": ["Decision", "Re-plan request", "Feed update"],
        "tools": ["Graph interrupt", "Audit trail"],
    },
    "traveler_notification": {
        "title": "Traveler Notification", "kind": "agent", "icon": "send",
        "role": "Executes the approved plan on the schedule and sends personalised, multilingual messages with self-service rebooking links.",
        "inputs": ["Approved plan", "Passenger outcomes", "Language & channel preferences"],
        "outputs": ["Notifications", "Schedule updates", "Assisted-call queue"],
        "tools": ["Template generator", "Channel router", "Plan executor", "Language model"],
    },
}


def build_graph():
    g = StateGraph(RecoveryState)
    g.add_node("detection", detection_node)
    g.add_node("impact_analysis", impact_node)
    g.add_node("infra_triage", infra_node)
    g.add_node("recovery_planner", recovery_node)
    g.add_node("tradeoff_analyst", tradeoff_node)
    g.add_node("controller_approval", approval_node,
               destinations=("traveler_notification", "recovery_planner", "impact_analysis", "infra_triage", END))
    g.add_node("traveler_notification", notification_node)

    g.add_edge(START, "detection")
    g.add_conditional_edges("detection", route_after_detection, ["impact_analysis", "infra_triage", END])
    g.add_edge("impact_analysis", "recovery_planner")
    g.add_edge("infra_triage", "recovery_planner")
    g.add_edge("recovery_planner", "tradeoff_analyst")
    g.add_edge("tradeoff_analyst", "controller_approval")
    g.add_edge("traveler_notification", END)
    return g.compile(checkpointer=InMemorySaver())


recovery_graph = build_graph()


def graph_structure() -> dict:
    drawable = recovery_graph.get_graph()
    nodes = []
    for node_id in drawable.nodes:
        meta = AGENT_REGISTRY.get(node_id)
        if meta:
            nodes.append({"id": node_id, **meta})
        else:
            nodes.append({"id": node_id, "title": "Start" if node_id == START else "End",
                          "kind": "terminal", "icon": "circle"})
    edges = [{"id": f"{e.source}->{e.target}", "source": e.source, "target": e.target,
              "conditional": bool(e.conditional), "label": e.data if isinstance(e.data, str) else None}
             for e in drawable.edges]
    return {"nodes": nodes, "edges": edges}
