from langgraph.graph import END, StateGraph

from app.graph.nodes import (
    generate,
    needs_revision,
    recall_memory,
    retrieve,
    review,
    route_entry,
    summarize_and_classify,
)
from app.graph.state import EmailState
from app.services.memory import checkpointer, store


def build_graph():
    graph = StateGraph(EmailState)

    graph.add_node("summarize_and_classify", summarize_and_classify)
    graph.add_node("recall_memory", recall_memory)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_node("review", review)

    # Regenerate enters straight at "generate" (see route_entry).
    graph.set_conditional_entry_point(
        route_entry, {"summarize_and_classify": "summarize_and_classify", "generate": "generate"}
    )
    graph.add_edge("summarize_and_classify", "recall_memory")
    graph.add_edge("recall_memory", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "review")

    # The review node can loop back to "generate" (self-correction) instead of
    # always ending — this is the bit that's actually worth showing a
    # recruiter: it's not just a linear chain.
    #
    # No "remember" node here - cross-session memory is written once from
    # handle_approval() in app/api/main.py, not once per regenerate iteration.
    graph.add_conditional_edges("review", needs_revision, {"generate": "generate", "end": END})

    # checkpointer = in-session (thread_id) memory; store = cross-session
    # (sender-keyed) memory - see app/services/memory.py.
    return graph.compile(checkpointer=checkpointer, store=store)


email_graph = build_graph()
