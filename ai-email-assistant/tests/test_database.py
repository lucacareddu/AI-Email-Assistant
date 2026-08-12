from app.services.database import create_email, get_email, update_email


def test_create_and_get_email():
    record = create_email(sender="a@b.com", subject="hi", body="hello")
    assert record["status"] == "pending"
    assert get_email(record["id"]) == record


def test_update_email():
    record = create_email(sender="a@b.com", subject="hi", body="hello")
    updated = update_email(record["id"], draft="a draft", status="sent")
    assert updated["draft"] == "a draft"
    assert updated["status"] == "sent"


def test_get_missing_email_returns_none():
    assert get_email(999999) is None
