from langgraph.graph import END, StateGraph

from app.graph.nodes import classify, generate, needs_revision, retrieve, review, summarize
from app.graph.state import EmailState


def build_graph():
    graph = StateGraph(EmailState)

    graph.add_node("summarize", summarize)
    graph.add_node("classify", classify)
    graph.add_node("retrieve", retrieve)
    graph.add_node("generate", generate)
    graph.add_node("review", review)

    graph.set_entry_point("summarize")
    graph.add_edge("summarize", "classify")
    graph.add_edge("classify", "retrieve")
    graph.add_edge("retrieve", "generate")
    graph.add_edge("generate", "review")

    # The review node can loop back to "generate" (self-correction) instead of
    # always ending — this is the bit that's actually worth showing a
    # recruiter: it's not just a linear chain.
    graph.add_conditional_edges("review", needs_revision, {"generate": "generate", "end": END})

    return graph.compile()


email_graph = build_graph()
