import hashlib
import hmac
import logging

from fastapi import FastAPI, Header, HTTPException, Request

from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Quorum")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/webhooks/github")
async def github_webhook(request: Request, x_hub_signature_256: str = Header(None)):
    if not x_hub_signature_256:
        raise HTTPException(status_code=401, detail="Missing signature")
    
    body = await request.body()
    secret = settings.github_webhook_secret.encode("utf-8")
    
    expected_signature = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    
    if not hmac.compare_digest(expected_signature, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    
    event_type = request.headers.get("X-GitHub-Event", "")
    if event_type == "pull_request":
        action = payload.get("action")
        if action in ["opened", "synchronize"]:
            pr_number = payload.get("pull_request", {}).get("number")
            repo_name = payload.get("repository", {}).get("full_name")
            logger.info(f"Received PR {action} event for repo {repo_name} PR #{pr_number}")
            
    return {"received": True}
