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
