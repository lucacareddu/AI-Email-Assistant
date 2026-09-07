"""Two kinds of memory for the graph, on top of the `emails` table in database.py
(which only tracks status - pending/sent/rejected - not what the graph itself saw):

- **In-session / short-term**: a LangGraph *checkpointer*, keyed by `thread_id`.
  One thread = one email's whole lifecycle (the initial draft plus any later
  "regenerate" requests for that same email). The graph resumes/records state
  under that thread instead of the API having to replay it by hand each call.

- **Cross-session / long-term**: a LangGraph *store*, keyed by the sender's
  address instead of thread_id. This is what actually survives across
  *different* emails from the same person - so a reply can say "we already
  covered this" instead of starting cold every time.

Both follow the same USE_POSTGRES toggle as the rest of the app (see
database.py, cache.py): Postgres-backed when available, sharing one
connection pool between the two; otherwise an in-process fallback so a demo/
dev run needs no DB - like the others, that fallback is lost on restart and
not shared across worker processes.
"""
import logging
import re

from app.config import settings

logger = logging.getLogger("api")

SENDER_MEMORY_NAMESPACE = ("sender_memory",)
# How many past interactions to keep per sender - a short rolling window,
# not an ever-growing log.
MAX_SENDER_MEMORY_ENTRIES = 5


def _psycopg_dsn(url: str) -> str:
    """SQLAlchemy DSNs look like postgresql+psycopg2://... - psycopg (v3,
    used by the checkpointer/store) wants the plain postgresql:// scheme."""
    return re.sub(r"^postgresql\+\w+://", "postgresql://", url)


if settings.use_postgres:
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool
    from langgraph.checkpoint.postgres import PostgresSaver
    from langgraph.store.postgres import PostgresStore

    # One pool, shared by the checkpointer (thread memory) and the store
    # (sender memory) - they use different tables, no reason to open two.
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
    # USE_POSTGRES=false - in-process only, no DB needed. Data is lost on
    # every restart; fine for a quick demo, not for anything you'd rely on.
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.store.memory import InMemoryStore

    logger.warning(
        "USE_POSTGRES=false: thread memory and sender memory are in-process only, "
        "lost on every restart and not shared across workers"
    )

    checkpointer = MemorySaver()
    store = InMemoryStore()

    def init_memory():
        pass


def recall_sender_memory(sender: str) -> str:
    """Cross-session recall: what do we remember about this sender from
    *previous* emails, if anything?

    The sender's address is the store *key*, not part of the namespace -
    LangGraph namespace labels can't contain periods, which email addresses
    always do (the domain's dot, at least)."""
    item = store.get(SENDER_MEMORY_NAMESPACE, sender)
    if not item:
        return ""
    entries = item.value.get("entries", [])
    if not entries:
        return ""
    return "\n".join(f"- {entry}" for entry in entries)


def remember_sender_interaction(sender: str, entry: str) -> None:
    """Append this interaction to the sender's cross-session memory, keeping
    only the last MAX_SENDER_MEMORY_ENTRIES so it doesn't grow unbounded."""
    item = store.get(SENDER_MEMORY_NAMESPACE, sender)
    entries = list(item.value.get("entries", [])) if item else []
    entries.append(entry)
    entries = entries[-MAX_SENDER_MEMORY_ENTRIES:]
    store.put(SENDER_MEMORY_NAMESPACE, sender, {"entries": entries})
