from langgraph.graph import StateGraph, START, END
from app.graph.state import SentinelState
from app.graph.nodes import make_nodes, route_gate, route_after_approval


def build_graph(checkpointer, *, executor_mod, adapter, settings):
    nodes = make_nodes(executor_mod, adapter, settings)
    g = StateGraph(SentinelState)
    for name, fn in nodes.items():
        g.add_node(name, fn)
    g.add_edge(START, "plan")
    g.add_edge("plan", "act")
    g.add_edge("act", "reflect")
    g.add_conditional_edges("reflect", route_gate,
                            {"approval": "approval", "finish": "finish", "act": "act"})
    g.add_conditional_edges("approval", route_after_approval,
                            {"execute": "execute", "finish": "finish"})
    g.add_edge("execute", "finish")
    g.add_edge("finish", END)
    return g.compile(checkpointer=checkpointer)
