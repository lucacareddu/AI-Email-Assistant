import json

from app.graph.nodes import _strip_code_fence, needs_revision


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
