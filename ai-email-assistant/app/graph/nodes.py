import json
import logging
import re
import time

import httpx

from app.config import settings
from app.graph.prompts import (
    GENERATE_PROMPT,
    REVIEW_PROMPT,
    SUMMARIZE_AND_CLASSIFY_PROMPT,
    SUMMARIZE_AND_CLASSIFY_SCHEMA,
)
from app.graph.state import EmailState
from app.rag.retriever import similarity_search
from app.services.memory import recall_sender_memory, remember_sender_interaction

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
    """Calls the Gemini API (plain HTTP - its REST API is simple enough not
    to need a client library)."""
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
    """Like _chat, but constrains Gemini's response to the given JSON schema
    (Gemini's native structured-output support), instead of asking for JSON
    in the prompt text and hoping the model complies."""
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
    """Summarize and classify in one call - classify only ever needed the
    subject and the summary this same call just produced, so there was no
    reason to make it a separate LLM round-trip."""
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


def recall_memory(state: EmailState) -> dict:
    """Cross-session recall: pull whatever we remember about this sender from
    *previous*, separate emails (see app/services/memory.py). This is not the
    in-session/thread state LangGraph already carries between the nodes below
    - it's memory that outlives this one thread entirely."""
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
            sender_memory=state.get("sender_memory") or "Nessuna interazione precedente nota.",
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


def remember(state: EmailState) -> dict:
    """Cross-session write-back: runs once the review loop is done, so we
    only persist the final accepted draft's summary - not every intermediate
    self-correction attempt. This is what recall_memory (above) reads back
    the next time this same sender emails in, on a different thread."""
    entry = f"Oggetto: {state['subject']} | Categoria: {state.get('category', 'other')} | Riassunto: {state.get('summary', '')}"
    remember_sender_interaction(state["sender"], entry)
    logger.info("[email %s] sender memory updated for %s", state.get("email_id"), state["sender"])
    return {"memory_saved": True}


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
