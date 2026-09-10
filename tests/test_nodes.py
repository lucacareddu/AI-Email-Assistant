import json
from unittest.mock import patch

from app.graph.nodes import _strip_code_fence, generate, needs_revision


def test_strip_code_fence_removes_multiline_fence():
    raw = '```json\n{"score": 9, "notes": "ok"}\n```'
    assert json.loads(_strip_code_fence(raw)) == {"score": 9, "notes": "ok"}


def test_strip_code_fence_removes_single_line_fence():
    raw = '```json {"score": 7, "notes": "fine"} ```'
    assert json.loads(_strip_code_fence(raw)) == {"score": 7, "notes": "fine"}


def test_strip_code_fence_passthrough_when_no_fence():
    raw = '{"score": 5, "notes": "plain"}'
    assert json.loads(_strip_code_fence(raw)) == {"score": 5, "notes": "plain"}


def test_needs_revision_loops_back_on_low_score():
    assert needs_revision({"review_score": 5, "review_attempts": 1}) == "generate"


def test_needs_revision_ends_on_high_score():
    assert needs_revision({"review_score": 9, "review_attempts": 1}) == "end"


def test_needs_revision_ends_when_attempts_exhausted():
    assert needs_revision({"review_score": 3, "review_attempts": 2}) == "end"


_BASE_STATE = {"subject": "s", "body": "b", "category": "support", "context": "c", "sender_memory": ""}


def test_generate_first_pass_uses_generate_prompt():
    with patch("app.graph.nodes._chat", return_value="draft") as chat:
        generate(dict(_BASE_STATE))
    prompt = chat.call_args.args[0]
    assert "INDICAZIONI DEL REVISORE" not in prompt


def test_generate_with_review_notes_and_prior_draft_uses_revise_prompt():
    state = {**_BASE_STATE, "draft": "bozza vecchia", "review_notes": "Sii più formale"}
    with patch("app.graph.nodes._chat", return_value="draft") as chat:
        generate(state)
    prompt = chat.call_args.args[0]
    assert "INDICAZIONI DEL REVISORE" in prompt
    assert "bozza vecchia" in prompt
    assert "Sii più formale" in prompt
