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
