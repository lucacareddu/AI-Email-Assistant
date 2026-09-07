from langgraph.graph import END, StateGraph

from app.graph.nodes import (
    generate,
    needs_revision,
    recall_memory,
    retrieve,
    review,
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

    graph.set_entry_point("summarize_and_classify")
    graph.add_edge("summarize_and_classify", "recall_memory")
    graph.add_edge("recall_memory", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "review")

    # The review node can loop back to "generate" (self-correction) instead of
    # always ending — this is the bit that's actually worth showing a
    # recruiter: it's not just a linear chain.
    #
    # Note there's no "remember" node here: this graph re-runs from its entry
    # point on every /approve regenerate too (same thread_id, admin tips or
    # not - see app/api/main.py), so "review passed" happens once per
    # iteration, not once per email. Writing cross-session memory here would
    # both spam a sender's history with one entry per iteration and, worse,
    # have recall_memory read back an in-progress email as if it were a past
    # one. remember_sender_interaction() is instead called directly from
    # handle_approval() only once the email reaches a terminal state
    # (approve/reject) - see app/api/main.py.
    graph.add_conditional_edges("review", needs_revision, {"generate": "generate", "end": END})

    # checkpointer = in-session memory, keyed by the thread_id passed at
    # invoke() time (one thread per email - see app/api/main.py). store =
    # cross-session memory, keyed by sender address (see app/services/memory.py,
    # used directly by recall_memory above and by handle_approval() in
    # app/api/main.py). Both are Postgres-backed or in-process depending on
    # USE_POSTGRES.
    return graph.compile(checkpointer=checkpointer, store=store)


email_graph = build_graph()
