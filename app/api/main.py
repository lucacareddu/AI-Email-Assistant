import logging
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import settings
from app.graph.graph import email_graph
from app.logging_config import configure_logging
from app.services.database import create_email, get_email, init_db, update_email
from app.services.gmail import send_reply
from app.services.memory import init_memory, remember_sender_interaction

configure_logging()
logger = logging.getLogger("api")

app = FastAPI(title="AI Email Assistant")


@app.on_event("startup")
def startup():
    init_db()
    init_memory()
    logger.info("AI Email Assistant started, DB + thread/sender memory initialised")


def _thread_config(email_id: int) -> dict:
    """One LangGraph thread per email, shared across regenerate calls."""
    return {"configurable": {"thread_id": str(email_id)}}


def _remember(record: dict) -> None:
    """Cross-session write-back, called once per email at a terminal state."""
    entry = f"Oggetto: {record['subject']} | Categoria: {record.get('category', 'other')} | Riassunto: {record.get('summary', '')}"
    remember_sender_interaction(record["sender"], entry)
    logger.info("[email %s] sender memory updated for %s", record["id"], record["sender"])


# --- n8n connectivity logging -------------------------------------------------
# If n8n can't reach this server at all (wrong API_BASE_URL, firewall, n8n
# pointing at localhost when it should hit host.docker.internal, etc.) nothing
# below will ever run - that failure happens on n8n's side, check the HTTP
# Request node's execution log there. What we *can* catch here is every
# request that does arrive but is malformed or unauthenticated, which in
# practice is the more common "n8n is connected but something is wrong" case.


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    logger.warning(
        "Invalid body on %s from %s (if this was n8n, check the HTTP Request node's JSON): %s",
        request.url.path, request.client.host if request.client else "unknown", exc.errors(),
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    logger.exception("Unhandled error while processing %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


def _check_token(request: Request, x_webhook_token: Optional[str]):
    if x_webhook_token != settings.webhook_token:
        logger.warning(
            "Rejected call to %s from %s: missing/wrong X-Webhook-Token "
            "(check the Header Auth credential on the n8n HTTP Request node)",
            request.url.path, request.client.host if request.client else "unknown",
        )
        raise HTTPException(status_code=401, detail="Invalid webhook token")


class IncomingEmail(BaseModel):
    sender: str
    subject: str
    body: str


DEFAULT_REGENERATE_NOTE = "Nessuna indicazione specifica: proponi una variante alternativa del testo, con un taglio leggermente diverso ma ugualmente professionale."


class ApproveRequest(BaseModel):
    id: int
    action: str  # approve | refuse | regenerate
    notes: Optional[str] = None  # optional admin tip for regenerate; falls back to default


@app.post("/email")
def handle_email(
    request: Request,
    payload: IncomingEmail,
    x_webhook_token: Optional[str] = Header(default=None),
):
    """Called by n8n (Workflow 1) right after a new email is picked up from Gmail -
    but this just logs whoever actually called it, n8n or otherwise."""
    _check_token(request, x_webhook_token)
    logger.info(
        "/email called by %s - sender=%s subject=%s",
        request.client.host if request.client else "unknown", payload.sender, payload.subject,
    )

    record = create_email(sender=payload.sender, subject=payload.subject, body=payload.body)

    result = email_graph.invoke(
        {
            "email_id": record["id"],
            "sender": payload.sender,
            "subject": payload.subject,
            "body": payload.body,
            "review_attempts": 0,
            "review_notes": "",
        },
        config=_thread_config(record["id"]),
    )

    record = update_email(
        record["id"],
        summary=result["summary"],
        category=result["category"],
        draft=result["draft"],
        review_notes=result.get("review_notes", ""),
    )
    logger.info("[email %s] draft ready, status=%s", record["id"], record["status"])
    return record


@app.post("/approve")
def handle_approval(
    request: Request,
    payload: ApproveRequest,
    x_webhook_token: Optional[str] = Header(default=None),
):
    """Called by n8n (Workflow 2) after a human taps Approve / Reject / Regenerate on Telegram -
    but this just logs whoever actually called it, n8n or otherwise."""
    _check_token(request, x_webhook_token)
    logger.info(
        "/approve called by %s - id=%s action=%s",
        request.client.host if request.client else "unknown", payload.id, payload.action,
    )

    record = get_email(payload.id)
    if record is None:
        logger.warning("/approve referenced unknown email id=%s", payload.id)
        raise HTTPException(status_code=404, detail="Email not found")

    if record["status"] in ("sent", "refused"):
        logger.warning(
            "/approve got action=%s for id=%s but it's already %s, ignoring",
            payload.action, payload.id, record["status"],
        )
        raise HTTPException(status_code=409, detail=f"Email is already {record['status']}")

    if payload.action == "approve":
        send_reply(to=record["sender"], subject=record["subject"], body=record["draft"])
        record = update_email(payload.id, status="sent")
        _remember(record)
        logger.info("[email %s] reply sent via Gmail API", payload.id)

    elif payload.action == "refuse":
        record = update_email(payload.id, status="refused")
        _remember(record)
        logger.info("[email %s] refused by reviewer", payload.id)

    elif payload.action == "regenerate":
        admin_tip = (payload.notes or "").strip()
        review_notes = admin_tip or DEFAULT_REGENERATE_NOTE
        logger.info(
            "[email %s] regenerate requested (%s), re-running the graph",
            payload.id, f"admin tip: {admin_tip}" if admin_tip else "no tip, using default",
        )
        # Other fields resume from the checkpoint; "regenerate" routes to "generate".
        result = email_graph.invoke(
            {
                "review_attempts": 0,
                "review_notes": review_notes,
                "regenerate": True,
            },
            config=_thread_config(record["id"]),
        )
        record = update_email(payload.id, draft=result["draft"], category=result["category"])

    else:
        logger.warning("/approve got unknown action=%s for id=%s", payload.action, payload.id)
        raise HTTPException(status_code=400, detail="Unknown action")

    return record


@app.get("/health")
def health():
    return {"status": "ok"}