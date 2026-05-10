from dataclasses import asdict

from jasmine_v2.core.events import IncomingEvent
from jasmine_v2.core.graph import build_jasmine_graph


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_jasmine_graph()
    return _graph


def run_event(event: IncomingEvent) -> dict:
    graph = get_graph()

    initial_state = {
        "event": asdict(event),
        "errors": [],
        "debug_log": [],
    }

    return graph.invoke(initial_state)