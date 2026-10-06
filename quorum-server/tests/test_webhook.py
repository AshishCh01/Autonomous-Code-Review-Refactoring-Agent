import hashlib
import hmac
import json

from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)

def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_webhook_missing_signature():
    response = client.post("/webhooks/github", json={})
    assert response.status_code == 401

def test_webhook_invalid_signature():
    response = client.post(
        "/webhooks/github",
        json={},
        headers={"x-hub-signature-256": "sha256=invalid"}
    )
    assert response.status_code == 401

def test_webhook_valid_signature(monkeypatch):
    monkeypatch.setattr("app.api.main.settings.github_webhook_secret", "test_secret")
    
    payload = {
        "action": "opened",
        "pull_request": {"number": 123},
        "repository": {"full_name": "test/repo"}
    }
    body = json.dumps(payload).encode("utf-8")
    
    secret = b"test_secret"
    signature = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    
    response = client.post(
        "/webhooks/github",
        content=body,
        headers={
            "x-hub-signature-256": signature,
            "x-github-event": "pull_request",
            "content-type": "application/json"
        }
    )
    
    assert response.status_code == 200
    assert response.json() == {"received": True}
