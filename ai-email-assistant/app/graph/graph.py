from langgraph.graph import END, StateGraph

from app.graph.nodes import (
    classify,
    generate,
    needs_revision,
    recall_memory,
    remember,
    retrieve,
    review,
    summarize,
)
from app.graph.state import EmailState
from app.services.memory import checkpointer, store


def build_graph():
    graph = StateGraph(EmailState)

    graph.add_node("summarize", summarize)
    graph.add_node("classify", classify)
    graph.add_node("recall_memory", recall_memory)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_node("review", review)
    graph.add_node("remember", remember)

    graph.set_entry_point("summarize")
    graph.add_edge("summarize", "classify")
    graph.add_edge("classify", "recall_memory")
    graph.add_edge("recall_memory", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "review")

    # The review node can loop back to "generate" (self-correction) instead of
    # always ending — this is the bit that's actually worth showing a
    # recruiter: it's not just a linear chain. Once it's happy, "remember"
    # writes the final draft back to cross-session (sender-scoped) memory
    # before the run ends.
    graph.add_conditional_edges("review", needs_revision, {"generate": "generate", "end": "remember"})
    graph.add_edge("remember", END)

    # checkpointer = in-session memory, keyed by the thread_id passed at
    # invoke() time (one thread per email - see app/api/main.py). store =
    # cross-session memory, keyed by sender address (see app/services/memory.py,
    # used directly by the recall_memory/remember nodes above). Both are
    # Postgres-backed or in-process depending on USE_POSTGRES.
    return graph.compile(checkpointer=checkpointer, store=store)


email_graph = build_graph()
