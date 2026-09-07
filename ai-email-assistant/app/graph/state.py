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
    # emails (populated by recall_memory, written by remember - see
    # app/services/memory.py). Empty string if this is the first time we've
    # heard from them.
    sender_memory: str
    # Set by remember() once the final draft has been written back to
    # cross-session memory - LangGraph requires every node to write at least
    # one state key, and there's otherwise nothing left for this one to write.
    memory_saved: bool
