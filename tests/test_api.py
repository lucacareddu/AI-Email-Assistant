from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.main import app
from app.services.database import create_email

HEADERS = {"X-Webhook-Token": "test-webhook-token"}


def test_approve_rejects_wrong_token():
    with TestClient(app) as client:
        r = client.post(
            "/approve", json={"id": 1, "action": "refuse"},
            headers={"X-Webhook-Token": "wrong"},
        )
        assert r.status_code == 401


def test_approve_unknown_id_returns_404():
    with TestClient(app) as client:
        r = client.post("/approve", json={"id": 999999, "action": "refuse"}, headers=HEADERS)
        assert r.status_code == 404


def test_email_invalid_body_returns_422():
    with TestClient(app) as client:
        r = client.post("/email", json={"sender": "a@b.com"}, headers=HEADERS)  # missing subject/body
        assert r.status_code == 422


def test_email_happy_path_with_mocked_graph():
    fake_result = {"summary": "s", "category": "support", "draft": "d", "review_notes": ""}
    with TestClient(app) as client, patch("app.api.main.email_graph.invoke", return_value=fake_result):
        r = client.post(
            "/email", json={"sender": "a@b.com", "subject": "hi", "body": "hello"}, headers=HEADERS,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["draft"] == "d"
        assert body["status"] == "pending"


def test_approve_action_sends_via_gmail_and_marks_sent():
    record = create_email(sender="a@b.com", subject="hi", body="hello")

    with TestClient(app) as client, patch("app.api.main.send_reply") as mock_send:
        r = client.post(
            "/approve", json={"id": record["id"], "action": "approve"}, headers=HEADERS,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "sent"
        mock_send.assert_called_once()


def test_approve_action_refuses_and_marks_refused():
    record = create_email(sender="a@b.com", subject="hi", body="hello")

    with TestClient(app) as client:
        r = client.post(
            "/approve", json={"id": record["id"], "action": "refuse"}, headers=HEADERS,
        )
        assert r.status_code == 200
        assert r.json()["status"] == "refused"


def test_approve_writes_sender_memory_once():
    record = create_email(sender="remember-me@example.com", subject="hi", body="hello")

    with TestClient(app) as client, patch("app.api.main.send_reply"), \
            patch("app.api.main.remember_sender_interaction") as mock_remember:
        client.post("/approve", json={"id": record["id"], "action": "approve"}, headers=HEADERS)

        mock_remember.assert_called_once()
        assert mock_remember.call_args.args[0] == "remember-me@example.com"


def test_refuse_also_writes_sender_memory():
    record = create_email(sender="remember-me-too@example.com", subject="hi", body="hello")

    with TestClient(app) as client, patch("app.api.main.remember_sender_interaction") as mock_remember:
        client.post("/approve", json={"id": record["id"], "action": "refuse"}, headers=HEADERS)

        mock_remember.assert_called_once()
        assert mock_remember.call_args.args[0] == "remember-me-too@example.com"


def test_regenerate_does_not_write_sender_memory():
    """Memory is written once at approve/refuse, not per regenerate iteration."""
    record = create_email(sender="a@b.com", subject="hi", body="hello")
    fake_result = {"draft": "new draft", "category": "support"}

    with TestClient(app) as client, patch("app.api.main.email_graph.invoke", return_value=fake_result), \
            patch("app.api.main.remember_sender_interaction") as mock_remember:
        client.post("/approve", json={"id": record["id"], "action": "regenerate"}, headers=HEADERS)

        mock_remember.assert_not_called()


def test_approve_action_regenerates_with_mocked_graph():
    record = create_email(sender="a@b.com", subject="hi", body="hello")
    fake_result = {"draft": "new draft", "category": "support"}

    with TestClient(app) as client, patch("app.api.main.email_graph.invoke", return_value=fake_result):
        r = client.post(
            "/approve", json={"id": record["id"], "action": "regenerate"}, headers=HEADERS,
        )
        assert r.status_code == 200
        assert r.json()["draft"] == "new draft"


def test_regenerate_without_notes_uses_default_review_notes():
    record = create_email(sender="a@b.com", subject="hi", body="hello")
    fake_result = {"draft": "new draft", "category": "support"}

    with TestClient(app) as client, patch("app.api.main.email_graph.invoke", return_value=fake_result) as mock_invoke:
        client.post("/approve", json={"id": record["id"], "action": "regenerate"}, headers=HEADERS)

        sent_state = mock_invoke.call_args.args[0]
        assert sent_state["review_notes"] == "Il revisore umano ha richiesto una versione diversa."


def test_regenerate_with_admin_tip_passes_it_as_review_notes():
    record = create_email(sender="a@b.com", subject="hi", body="hello")
    fake_result = {"draft": "new draft", "category": "support"}

    with TestClient(app) as client, patch("app.api.main.email_graph.invoke", return_value=fake_result) as mock_invoke:
        client.post(
            "/approve",
            json={"id": record["id"], "action": "regenerate", "notes": "Sii più formale e più breve"},
            headers=HEADERS,
        )

        sent_state = mock_invoke.call_args.args[0]
        assert sent_state["review_notes"] == "Sii più formale e più breve"


def test_regenerate_with_blank_notes_falls_back_to_default():
    record = create_email(sender="a@b.com", subject="hi", body="hello")
    fake_result = {"draft": "new draft", "category": "support"}

    with TestClient(app) as client, patch("app.api.main.email_graph.invoke", return_value=fake_result) as mock_invoke:
        client.post(
            "/approve", json={"id": record["id"], "action": "regenerate", "notes": "   "}, headers=HEADERS,
        )

        sent_state = mock_invoke.call_args.args[0]
        assert sent_state["review_notes"] == "Il revisore umano ha richiesto una versione diversa."


def test_approve_unknown_action_returns_400():
    record = create_email(sender="a@b.com", subject="hi", body="hello")

    with TestClient(app) as client:
        r = client.post(
            "/approve", json={"id": record["id"], "action": "not-a-real-action"}, headers=HEADERS,
        )
        assert r.status_code == 400


def test_health_check():
    with TestClient(app) as client:
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}
