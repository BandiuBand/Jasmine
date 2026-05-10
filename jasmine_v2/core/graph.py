from langgraph.graph import StateGraph, END

from jasmine_v2.core.state import JasmineState
from jasmine_v2.nodes.normalize_event import normalize_event
from jasmine_v2.nodes.resolve_identity import resolve_identity
from jasmine_v2.nodes.route_intent import route_intent
from jasmine_v2.nodes.simple_response import simple_response
from jasmine_v2.nodes.finalize_response import finalize_response


def build_jasmine_graph():
    graph = StateGraph(JasmineState)

    graph.add_node("normalize_event", normalize_event)
    graph.add_node("resolve_identity", resolve_identity)
    graph.add_node("route_intent", route_intent)
    graph.add_node("simple_response", simple_response)
    graph.add_node("finalize_response", finalize_response)

    graph.set_entry_point("normalize_event")

    graph.add_edge("normalize_event", "resolve_identity")
    graph.add_edge("resolve_identity", "route_intent")
    graph.add_edge("route_intent", "simple_response")
    graph.add_edge("simple_response", "finalize_response")
    graph.add_edge("finalize_response", END)

    return graph.compile()