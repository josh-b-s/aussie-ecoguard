"""Offline tests for /chat: Dialogflow is replaced by a fake."""

import os

import pytest
from fastapi.testclient import TestClient

os.environ["COGNITO_REGION"] = "ap-southeast-2"
os.environ["COGNITO_USER_POOL_ID"] = "ap-southeast-2_TESTPOOL"
os.environ["COGNITO_APP_CLIENT_ID"] = "testclient123"

import chat  # noqa: E402
from auth import get_current_user  # noqa: E402
from main import app  # noqa: E402

calls = []


@pytest.fixture(autouse=True)
def fakes(monkeypatch):
    app.dependency_overrides[get_current_user] = lambda: {"sub": "user-1"}
    calls.clear()

    def fake_detect(session_id, text):
        calls.append((session_id, text))
        return {
            "reply": "Looking for foxes.",
            "intent": "search.by.tag",
            "confidence": 0.93,
            "parameters": {"animal": ["fox"]},
        }

    monkeypatch.setattr(chat, "detect_intent", fake_detect)
    yield
    app.dependency_overrides.clear()


client = TestClient(app)


def test_returns_reply_intent_and_parameters():
    r = client.post("/chat", json={"message": "show me foxes"})
    assert r.status_code == 200
    assert r.json() == {
        "reply": "Looking for foxes.",
        "intent": "search.by.tag",
        "confidence": 0.93,
        "parameters": {"animal": ["fox"]},
    }


def test_session_id_comes_from_the_token_not_the_client():
    client.post("/chat", json={"message": "hi", "session_id": "someone-else"})
    assert calls == [("user-1", "hi")]


def test_message_is_trimmed():
    client.post("/chat", json={"message": "  hello  "})
    assert calls[0][1] == "hello"


@pytest.mark.parametrize("bad", [{}, {"message": ""}, {"message": "   "}, {"message": "x" * 257}, {"message": 5}])
def test_bad_messages_return_400(bad):
    assert client.post("/chat", json=bad).status_code == 400
    assert calls == []


def test_dialogflow_failure_returns_502(monkeypatch):
    def boom(*_):
        raise chat.DialogflowError("down")

    monkeypatch.setattr(chat, "detect_intent", boom)
    r = client.post("/chat", json={"message": "hi"})
    assert r.status_code == 502
    assert "down" not in r.text


def test_requires_token():
    app.dependency_overrides.clear()
    assert client.post("/chat", json={"message": "hi"}).status_code == 401
