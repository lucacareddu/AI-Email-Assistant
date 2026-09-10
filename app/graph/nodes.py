import json
import logging
import re
import time

import httpx

from app.config import settings
from app.graph.prompts import (
    GENERATE_PROMPT,
    REVIEW_PROMPT,
    REVISE_PROMPT,
    SUMMARIZE_AND_CLASSIFY_PROMPT,
    SUMMARIZE_AND_CLASSIFY_SCHEMA,
)
from app.graph.state import EmailState
from app.rag.retriever import similarity_search
from app.services.memory import recall_sender_memory

MAX_REVIEW_ATTEMPTS = 2

logger = logging.getLogger("graph")


def _short(text: str, length: int = 120) -> str:
    text = (text or "").replace("\n", " ")
    return text if len(text) <= length else text[:length] + "..."


_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _strip_code_fence(text: str) -> str:
    """Strips Gemini's occasional ```json ... ``` wrapping before json.loads."""
    return _CODE_FENCE_RE.sub("", text.strip()).strip()


def _chat(prompt: str) -> str:
    """Plain-text Gemini call."""
    response = httpx.post(
        f"{settings.gemini_base_url}/{settings.chat_model}:generateContent",
        headers={
            "x-goog-api-key": settings.gemini_api_key,
            "Content-Type": "application/json",
        },
        json={
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"temperature": 0.3},
        },
        timeout=30,
    )
    if response.status_code >= 400:
        logger.error("Gemini API error %s: %s", response.status_code, response.text)
    response.raise_for_status()
    return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def _chat_json(prompt: str, schema: dict) -> dict:
    """Gemini call constrained to a JSON schema (native structured output)."""
    response = httpx.post(
        f"{settings.gemini_base_url}/{settings.chat_model}:generateContent",
        headers={
            "x-goog-api-key": settings.gemini_api_key,
            "Content-Type": "application/json",
        },
        json={
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.3,
                "responseMimeType": "application/json",
                "responseSchema": schema,
            },
        },
        timeout=30,
    )
    if response.status_code >= 400:
        logger.error("Gemini API error %s: %s", response.status_code, response.text)
    response.raise_for_status()
    text = response.json()["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def summarize_and_classify(state: EmailState) -> dict:
    """Summarize and classify in one LLM call instead of two."""
    start = time.perf_counter()
    result = _chat_json(
        SUMMARIZE_AND_CLASSIFY_PROMPT.format(subject=state["subject"], body=state["body"]),
        schema=SUMMARIZE_AND_CLASSIFY_SCHEMA,
    )
    summary, category = result["summary"], result["category"].lower()
    logger.info(
        "[email %s] summarize_and_classify done in %.2fs -> category=%s summary=%s",
        state.get("email_id"), time.perf_counter() - start, category, _short(summary),
    )
    return {"summary": summary, "category": category}


def route_entry(state: EmailState) -> str:
    """Regenerate skips straight to "generate"; everything else runs full."""
    return "generate" if state.get("regenerate") else "summarize_and_classify"


def recall_memory(state: EmailState) -> dict:
    """Cross-session recall of this sender's previous, separate emails."""
    start = time.perf_counter()
    memory = recall_sender_memory(state["sender"])
    logger.info(
        "[email %s] recall done in %.2fs -> %s",
        state.get("email_id"), time.perf_counter() - start,
        "found prior memory" if memory else "no prior memory for this sender",
    )
    return {"sender_memory": memory}


def retrieve(state: EmailState) -> dict:
    start = time.perf_counter()
    chunks = similarity_search(f"{state['subject']} {state['summary']}", k=4)
    context = "\n---\n".join(chunks) if chunks else "Nessun documento rilevante trovato."
    logger.info(
        "[email %s] retrieve done in %.2fs -> %d chunk(s) found",
        state.get("email_id"), time.perf_counter() - start, len(chunks),
    )
    if not chunks:
        logger.warning(
            "[email %s] retrieve found no documents - is the vector store empty? "
            "Run `python -m app.rag.ingest` if you haven't yet.",
            state.get("email_id"),
        )
    return {"context": context}


def generate(state: EmailState) -> dict:
    """First pass uses GENERATE_PROMPT; a review loop-back or a /approve regenerate
    (both carry review_notes + a prior draft) uses REVISE_PROMPT instead."""
    start = time.perf_counter()
    fields = dict(
        subject=state["subject"],
        body=state["body"],
        category=state.get("category", "other"),
        context=state.get("context", ""),
        sender_memory=state.get("sender_memory") or "Nessuna interazione precedente nota.",
    )
    review_notes, previous_draft = state.get("review_notes"), state.get("draft")
    if review_notes and previous_draft:
        mode = "revise"
        prompt = REVISE_PROMPT.format(previous_draft=previous_draft, review_notes=review_notes, **fields)
    else:
        mode = "generate"
        prompt = GENERATE_PROMPT.format(**fields)

    draft = _chat(prompt)
    logger.info(
        "[email %s] %s done in %.2fs (attempt %d) -> %s",
        state.get("email_id"), mode, time.perf_counter() - start,
        state.get("review_attempts", 0) + 1, _short(draft),
    )
    return {"draft": draft}


def review(state: EmailState) -> dict:
    start = time.perf_counter()
    raw = _chat(REVIEW_PROMPT.format(body=state["body"], draft=state["draft"]))
    try:
        parsed = json.loads(_strip_code_fence(raw))
        score, notes = int(parsed["score"]), parsed.get("notes", "")
    except (json.JSONDecodeError, KeyError, ValueError):
        # Se il modello non rispetta il formato JSON richiesto, non blocchiamo
        # il flusso: accettiamo la bozza così com'è.
        logger.warning(
            "[email %s] review response wasn't valid JSON, accepting draft as-is: %s",
            state.get("email_id"), _short(raw),
        )
        score, notes = 10, ""

    logger.info(
        "[email %s] review done in %.2fs -> score=%s notes=%s",
        state.get("email_id"), time.perf_counter() - start, score, _short(notes),
    )

    return {
        "review_score": score,
        "review_notes": notes,
        "review_attempts": state.get("review_attempts", 0) + 1,
    }


def needs_revision(state: EmailState) -> str:
    if state["review_score"] < 7 and state["review_attempts"] < MAX_REVIEW_ATTEMPTS:
        logger.info(
            "[email %s] review score %s < 7 (attempt %d/%d) -> looping back to generate",
            state.get("email_id"), state["review_score"],
            state["review_attempts"], MAX_REVIEW_ATTEMPTS,
        )
        return "generate"
    logger.info(
        "[email %s] review passed (score=%s, attempts=%d) -> done",
        state.get("email_id"), state["review_score"], state["review_attempts"],
    )
    return "end"
