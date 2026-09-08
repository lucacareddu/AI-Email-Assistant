"""In-session (thread_id) and cross-session (sender-keyed) memory for the graph."""
import logging
import re

from app.config import settings

logger = logging.getLogger("api")

SENDER_MEMORY_NAMESPACE = ("sender_memory",)
MAX_SENDER_MEMORY_ENTRIES = 5  # rolling window per sender, not an ever-growing log


def _psycopg_dsn(url: str) -> str:
    """SQLAlchemy's postgresql+psycopg2:// -> plain postgresql:// for psycopg (v3)."""
    return re.sub(r"^postgresql\+\w+://", "postgresql://", url)


if settings.use_postgres:
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
    from langgraph.checkpoint.postgres import PostgresSaver
    from langgraph.store.postgres import PostgresStore

    # Shared by the checkpointer and the store - different tables, one pool.
    _pool = ConnectionPool(
        _psycopg_dsn(settings.database_url),
        min_size=1,
        max_size=5,
        kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
        open=False,
    )

    checkpointer = PostgresSaver(_pool)
    store = PostgresStore(_pool)

    def init_memory():
        _pool.open()
        checkpointer.setup()
        store.setup()
        logger.info("Postgres checkpointer + store initialised (thread memory + sender memory)")

else:
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.store.memory import InMemoryStore

    logger.warning("USE_POSTGRES=false: thread/sender memory are in-process only, lost on restart")

    checkpointer = MemorySaver()
    store = InMemoryStore()

    def init_memory():
        pass


def recall_sender_memory(sender: str) -> str:
    """What we remember about this sender from previous emails, if anything."""
    item = store.get(SENDER_MEMORY_NAMESPACE, sender)
    if not item:
        return ""
    entries = item.value.get("entries", [])
    if not entries:
        return ""
    return "\n".join(f"- {entry}" for entry in entries)


def remember_sender_interaction(sender: str, entry: str) -> None:
    """Append to the sender's memory, keeping only the last N entries."""
    item = store.get(SENDER_MEMORY_NAMESPACE, sender)
    entries = list(item.value.get("entries", [])) if item else []
    entries.append(entry)
    entries = entries[-MAX_SENDER_MEMORY_ENTRIES:]
    store.put(SENDER_MEMORY_NAMESPACE, sender, {"entries": entries})
