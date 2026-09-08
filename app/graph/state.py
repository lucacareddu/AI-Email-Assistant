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

    # Cross-session memory recalled for this sender (app/services/memory.py).
    sender_memory: str

    # True only on a /approve regenerate - routes entry straight to "generate".
    regenerate: bool
