from typing import TypedDict


class EmailState(TypedDict):
    email_id: int
    sender: str
    subject: str
    body: str

    summary: str
    category: str
    context: str
    draft: str

    review_score: int
    review_notes: str
    review_attempts: int

    # Cross-session memory: what we recall about this sender from *previous*
    # emails (populated by recall_memory - see app/services/memory.py).
    # Writing it back is *not* a graph node - see handle_approval() in
    # app/api/main.py for why. Empty string if this is the first time we've
    # heard from this sender.
    sender_memory: str

    # True only on the invoke() call for a /approve regenerate (see
    # app/api/main.py) - routes the graph's entry point straight to
    # "generate" (see route_entry in nodes.py), skipping re-summarize,
    # re-classify, re-recall and re-retrieve for what's still the same
    # email. summary/category/context/sender_memory are resumed unchanged
    # from this thread's last checkpoint either way.
    regenerate: bool
