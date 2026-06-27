import json
import logging
import re
import time

import httpx

from app.config import settings
from app.graph.prompts import (
    CLASSIFY_PROMPT,
    GENERATE_PROMPT,
    REVIEW_PROMPT,
    SUMMARIZE_PROMPT,
)
from app.graph.state import EmailState
from app.rag.retriever import similarity_search

MAX_REVIEW_ATTEMPTS = 2

logger = logging.getLogger("graph")


def _short(text: str, length: int = 120) -> str:
    text = (text or "").replace("\n", " ")
    return text if len(text) <= length else text[:length] + "..."


_CODE_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _strip_code_fence(text: str) -> str:
    """Gemini sometimes wraps JSON answers in ```json ... ``` even when asked
    not to. Strip that before calling json.loads, instead of just giving up."""
    return _CODE_FENCE_RE.sub("", text.strip()).strip()


def _chat(prompt: str) -> str:
    """Calls Gemini's generateContent endpoint directly via HTTP.

    We don't use the google-genai SDK here on purpose: a plain HTTP call is
    explicit and easy to debug, and it's one less moving part to misconfigure.
    """
    # response = httpx.post(
    #     f"{settings.gemini_base_url}/{settings.chat_model}:generateContent",
    #     headers={
    #         "x-goog-api-key": settings.gemini_api_key,
    #         "Content-Type": "application/json",
    #     },
    #     json={
    #         "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    #         "generationConfig": {"temperature": 0.3},
    #     },
    #     timeout=30,
    # )
    # if response.status_code >= 400:
    #     logger.error("Gemini API error %s: %s", response.status_code, response.text)
    # response.raise_for_status()
    return "Good" #response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()


def summarize(state: EmailState) -> dict:
    # start = time.perf_counter()
    # summary = _chat(SUMMARIZE_PROMPT.format(subject=state["subject"], body=state["body"]))
    # logger.info(
    #     "[email %s] summarize done in %.2fs -> %s",
    #     state.get("email_id"), time.perf_counter() - start, _short(summary),
    # )
    return {"summary": "fine"} #"summary}


def classify(state: EmailState) -> dict:
    # start = time.perf_counter()
    # category = _chat(
    #     CLASSIFY_PROMPT.format(subject=state["subject"], summary=state["summary"])
    # ).lower()
    # logger.info(
    #     "[email %s] classify done in %.2fs -> %s",
    #     state.get("email_id"), time.perf_counter() - start, category,
    # )
    return {"category": "nice"}#category}


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
    start = time.perf_counter()
    revision_note = (
        f"Nota del revisore, correggi questi aspetti: {state['review_notes']}"
        if state.get("review_notes")
        else ""
    )
    draft = _chat(
        GENERATE_PROMPT.format(
            subject=state["subject"],
            body=state["body"],
            category=state.get("category", "other"),
            context=state.get("context", ""),
            revision_note=revision_note,
        )
    )
    logger.info(
        "[email %s] generate done in %.2fs (attempt %d) -> %s",
        state.get("email_id"), time.perf_counter() - start,
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