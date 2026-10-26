"""POST /chat: send the user's message to a Dialogflow ES agent.

The browser never talks to Dialogflow and never holds a Google key. It sends the
user's Cognito ID token (Bearer) to this route; Cloud Run verifies it and calls
Dialogflow with its own service account (Application Default Credentials).

The Dialogflow session id is the user's Cognito `sub`, derived on the server, so
a client cannot read or continue another user's conversation.
"""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import get_current_user

log = logging.getLogger("chat")
router = APIRouter()

DEFAULT_PROJECT = "ecoguard-g11-14145"
MAX_MESSAGE_CHARS = 256  # Dialogflow ES limit for a text query


class DialogflowError(RuntimeError):
    """The Dialogflow call failed."""


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)


_client = None


def detect_intent(session_id: str, text: str) -> dict:
    """Call Dialogflow ES detectIntent and return a plain dict."""
    global _client
    try:
        from google.cloud import dialogflow_v2 as dialogflow
        from google.protobuf.json_format import MessageToDict

        if _client is None:
            _client = dialogflow.SessionsClient()
        project = os.environ.get("DIALOGFLOW_PROJECT_ID", DEFAULT_PROJECT)
        language = os.environ.get("DIALOGFLOW_LANGUAGE", "en")
        session = _client.session_path(project, session_id)
        query = dialogflow.QueryInput(
            text=dialogflow.TextInput(text=text, language_code=language)
        )
        response = _client.detect_intent(
            request={"session": session, "query_input": query}, timeout=15
        )
        result = response.query_result
        return {
            "reply": result.fulfillment_text,
            "intent": result.intent.display_name or None,
            "confidence": round(float(result.intent_detection_confidence), 3),
            "parameters": MessageToDict(result._pb.parameters),
        }
    except Exception as exc:
        raise DialogflowError("dialogflow request failed") from exc


@router.post("/chat")
def chat(req: ChatRequest, user: dict = Depends(get_current_user)) -> dict:
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message must not be empty")
    try:
        return detect_intent(user["sub"], message)
    except DialogflowError:
        # Do not log the message text: it may contain personal details.
        log.exception("Dialogflow call failed")
        raise HTTPException(status_code=502, detail="Chatbot is unavailable")
