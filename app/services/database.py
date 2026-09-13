import logging
from datetime import datetime, timezone
from itertools import count

from app.config import settings

logger = logging.getLogger("api")


if settings.use_postgres:
    from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
    from sqlalchemy.orm import declarative_base, sessionmaker

    engine = create_engine(settings.database_url, future=True)
    SessionLocal = sessionmaker(bind=engine, future=True)
    Base = declarative_base()

    class Email(Base):
        __tablename__ = "emails"

        id = Column(Integer, primary_key=True)
        sender = Column(String, nullable=False)
        subject = Column(String, nullable=False)
        body = Column(Text, nullable=False)
        message_id = Column(String)  # original Gmail Message-ID header, for In-Reply-To/References
        thread_id = Column(String)  # original Gmail threadId, so the reply lands in the same thread

        summary = Column(Text)
        category = Column(String)
        draft = Column(Text)
        review_notes = Column(Text)
        status = Column(String, default="pending")  # pending | sent | refused

        created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
        updated_at = Column(
            DateTime,
            default=lambda: datetime.now(timezone.utc),
            onupdate=lambda: datetime.now(timezone.utc),
        )

    def init_db():
        Base.metadata.create_all(engine)

    def _as_dict(email: Email) -> dict:
        return {
            "id": email.id,
            "sender": email.sender,
            "subject": email.subject,
            "body": email.body,
            "message_id": email.message_id,
            "thread_id": email.thread_id,
            "summary": email.summary,
            "category": email.category,
            "draft": email.draft,
            "review_notes": email.review_notes,
            "status": email.status,
        }

    def create_email(sender: str, subject: str, body: str, message_id: str | None = None, thread_id: str | None = None) -> dict:
        with SessionLocal() as session:
            email = Email(sender=sender, subject=subject, body=body, message_id=message_id, thread_id=thread_id)
            session.add(email)
            session.commit()
            session.refresh(email)
            return _as_dict(email)

    def get_email(email_id: int) -> dict | None:
        with SessionLocal() as session:
            email = session.get(Email, email_id)
            return _as_dict(email) if email else None

    def update_email(email_id: int, **fields) -> dict:
        with SessionLocal() as session:
            email = session.get(Email, email_id)
            for key, value in fields.items():
                setattr(email, key, value)
            session.commit()
            session.refresh(email)
            return _as_dict(email)

else:
    # USE_POSTGRES=false - plain in-memory dict, no DB needed. Data is lost on
    # every restart; fine for a quick demo, not for anything you'd rely on.
    logger.warning("USE_POSTGRES=false: using in-memory storage, data will NOT persist across restarts")

    _store: dict[int, dict] = {}
    _id_counter = count(1)

    def init_db():
        pass

    def create_email(sender: str, subject: str, body: str, message_id: str | None = None, thread_id: str | None = None) -> dict:
        email_id = next(_id_counter)
        record = {
            "id": email_id,
            "sender": sender,
            "subject": subject,
            "body": body,
            "message_id": message_id,
            "thread_id": thread_id,
            "summary": None,
            "category": None,
            "draft": None,
            "review_notes": None,
            "status": "pending",
        }
        _store[email_id] = record
        return dict(record)

    def get_email(email_id: int) -> dict | None:
        record = _store.get(email_id)
        return dict(record) if record else None

    def update_email(email_id: int, **fields) -> dict:
        record = _store[email_id]
        record.update(fields)
        return dict(record)
