"""USE_POSTGRES=false in conftest.py, so these exercise the in-process
InMemoryStore fallback - same code path recall_memory/remember (app/graph/
nodes.py) call in production, just backed by memory instead of Postgres."""
from app.services.memory import recall_sender_memory, remember_sender_interaction, store


def test_recall_returns_empty_string_for_unknown_sender():
    assert recall_sender_memory("stranger@example.com") == ""


def test_remember_then_recall_roundtrips():
    sender = "regular@example.com"
    remember_sender_interaction(sender, "Oggetto: ciao | Categoria: sales | Riassunto: prima email")

    memory = recall_sender_memory(sender)

    assert "prima email" in memory


def test_remember_keeps_only_last_n_entries():
    sender = "chatty@example.com"
    for i in range(10):
        remember_sender_interaction(sender, f"entry-{i}")

    memory = recall_sender_memory(sender)

    assert "entry-9" in memory
    assert "entry-0" not in memory


def test_sender_memory_is_scoped_per_sender():
    remember_sender_interaction("a@example.com", "only for a")
    remember_sender_interaction("b@example.com", "only for b")

    assert "only for a" in recall_sender_memory("a@example.com")
    assert "only for b" not in recall_sender_memory("a@example.com")


def test_store_is_the_langgraph_in_memory_store_fallback():
    from langgraph.store.memory import InMemoryStore

    assert isinstance(store, InMemoryStore)
