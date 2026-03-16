"""GitHub Webhook integration for PatchFlow."""
import hmac
import hashlib
import secrets
from fastapi import APIRouter, HTTPException, Depends, Header, Request, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from core.database import get_db
from core.config import settings
from models import User, Repository, WebhookEvent
from api.routes.auth import get_current_user as get_current_user_from_token
import httpx
import structlog

logger = structlog.get_logger()
router = APIRouter(tags=["GitHub Webhooks"])

WEBHOOK_EVENTS = ["push", "pull_request", "repository"]


async def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify GitHub webhook signature."""
    if not signature or not signature.startswith("sha256="):
        return False
    
    expected_signature = "sha256=" + hmac.new(
        secret.encode(),
        payload,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(signature, expected_signature)


@router.post("/webhook/{repo_id}")
async def github_webhook(
    request: Request,
    repo_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    x_github_event: str = Header(None, alias="X-GitHub-Event"),
    x_github_delivery: str = Header(None, alias="X-GitHub-Delivery"),
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256"),
):
    """Receive GitHub webhook events."""
    # Get repository
    result = await db.execute(select(Repository).where(Repository.id == repo_id))
    repo = result.scalar_one_or_none()
    
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    if not repo.webhook_secret:
        raise HTTPException(status_code=400, detail="Webhook not configured for this repository")
    
    # Read raw payload
    payload_bytes = await request.body()
    
    # Verify signature
    if x_hub_signature_256 and not await verify_webhook_signature(
        payload_bytes, x_hub_signature_256, repo.webhook_secret
    ):
        logger.warning("Invalid webhook signature", repo_id=repo_id, delivery_id=x_github_delivery)
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    # Parse payload
    payload = await request.json()
    
    # Extract push event details
    ref = payload.get("ref")
    before_commit = payload.get("before")
    after_commit = payload.get("after")
    pusher = payload.get("pusher", {})
    commits = payload.get("commits", [])
    
    commit_message = None
    if commits:
        commit_message = commits[0].get("message", "")
    
    # Create webhook event record
    webhook_event = WebhookEvent(
        repository_id=repo_id,
        event_type=x_github_event or "unknown",
        delivery_id=x_github_delivery,
        payload=payload,
        action=payload.get("action"),
        ref=ref,
        before_commit=before_commit,
        after_commit=after_commit,
        pusher_name=pusher.get("name"),
        pusher_email=pusher.get("email"),
        commit_message=commit_message,
        status="received"
    )
    
    db.add(webhook_event)
    await db.commit()
    
    logger.info(
        "Webhook received",
        repo_id=repo_id,
        event_type=x_github_event,
        delivery_id=x_github_delivery,
        ref=ref
    )
    
    # Trigger scan for push events on default branch
    if x_github_event == "push" and ref == f"refs/heads/{repo.default_branch}":
        background_tasks.add_task(trigger_repository_scan, repo_id, after_commit, db)
        webhook_event.scan_triggered = True
        webhook_event.status = "processing"
        await db.commit()
    
    return {"status": "received", "event_id": webhook_event.id}


async def trigger_repository_scan(repo_id: str, commit_sha: str, db: AsyncSession):
    """Trigger a security scan for a repository."""
    try:
        logger.info("Starting repository scan", repo_id=repo_id, commit_sha=commit_sha)
        
        # TODO: Implement actual scanning logic
        # This would:
        # 1. Clone the repository
        # 2. Run Snyk/Trivy/dependency check
        # 3. Create Vulnerability records
        # 4. Trigger AI triage
        
        # For now, just update the timestamp
        result = await db.execute(select(Repository).where(Repository.id == repo_id))
        repo = result.scalar_one_or_none()
        if repo:
            from datetime import datetime
            repo.last_scan_at = datetime.utcnow()
            await db.commit()
        
        logger.info("Repository scan completed", repo_id=repo_id)
        
    except Exception as e:
        logger.error("Repository scan failed", repo_id=repo_id, error=str(e))


@router.post("/repos/{repo_id}/webhook/register")
async def register_webhook(
    repo_id: str,
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """Register a webhook with GitHub for this repository."""
    # Get repository
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id, Repository.owner_id == current_user.id)
    )
    repo = result.scalar_one_or_none()
    
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    if not current_user.github_token:
        raise HTTPException(status_code=401, detail="GitHub not connected")
    
    # Generate webhook secret
    webhook_secret = secrets.token_urlsafe(32)
    
    # Webhook URL (for local testing, use ngrok or similar)
    # In production: https://api.patchflow.ai/webhooks/github/{repo_id}
    webhook_url = f"http://localhost:8000/webhooks/github/{repo_id}"
    
    # Register with GitHub
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"https://api.github.com/repos/{repo.full_name}/hooks",
            headers={
                "Authorization": f"Bearer {current_user.github_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            json={
                "name": "web",
                "active": True,
                "events": WEBHOOK_EVENTS,
                "config": {
                    "url": webhook_url,
                    "content_type": "json",
                    "secret": webhook_secret,
                    "insecure_ssl": "0"
                }
            }
        )
        
        if response.status_code not in [200, 201]:
            error_detail = response.json().get("message", "Failed to create webhook")
            raise HTTPException(status_code=400, detail=error_detail)
        
        webhook_data = response.json()
    
    # Save webhook info to repository
    repo.webhook_id = str(webhook_data["id"])
    repo.webhook_secret = webhook_secret
    repo.webhook_url = webhook_url
    repo.webhook_events = WEBHOOK_EVENTS
    
    await db.commit()
    
    logger.info("Webhook registered", repo_id=repo_id, webhook_id=repo.webhook_id)
    
    return {
        "status": "registered",
        "webhook_id": repo.webhook_id,
        "events": WEBHOOK_EVENTS,
        "url": webhook_url
    }


@router.delete("/repos/{repo_id}/webhook")
async def delete_webhook(
    repo_id: str,
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db)
):
    """Delete the GitHub webhook for this repository."""
    # Get repository
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id, Repository.owner_id == current_user.id)
    )
    repo = result.scalar_one_or_none()
    
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    if not repo.webhook_id:
        raise HTTPException(status_code=400, detail="No webhook registered")
    
    if not current_user.github_token:
        raise HTTPException(status_code=401, detail="GitHub not connected")
    
    # Delete from GitHub
    async with httpx.AsyncClient() as client:
        response = await client.delete(
            f"https://api.github.com/repos/{repo.full_name}/hooks/{repo.webhook_id}",
            headers={
                "Authorization": f"Bearer {current_user.github_token}",
                "Accept": "application/vnd.github.v3+json"
            }
        )
        
        if response.status_code not in [200, 204, 404]:
            error_detail = response.json().get("message", "Failed to delete webhook")
            raise HTTPException(status_code=400, detail=error_detail)
    
    # Clear webhook info
    repo.webhook_id = None
    repo.webhook_secret = None
    repo.webhook_url = None
    repo.webhook_events = []
    
    await db.commit()
    
    logger.info("Webhook deleted", repo_id=repo_id)
    
    return {"status": "deleted"}


@router.get("/repos/{repo_id}/webhook/events")
async def list_webhook_events(
    repo_id: str,
    current_user: User = Depends(get_current_user_from_token),
    db: AsyncSession = Depends(get_db),
    limit: int = 50
):
    """List recent webhook events for a repository."""
    # Verify repository ownership
    result = await db.execute(
        select(Repository).where(Repository.id == repo_id, Repository.owner_id == current_user.id)
    )
    repo = result.scalar_one_or_none()
    
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    
    # Get events
    result = await db.execute(
        select(WebhookEvent)
        .where(WebhookEvent.repository_id == repo_id)
        .order_by(WebhookEvent.received_at.desc())
        .limit(limit)
    )
    events = result.scalars().all()
    
    return {
        "events": [
            {
                "id": event.id,
                "event_type": event.event_type,
                "action": event.action,
                "ref": event.ref,
                "pusher_name": event.pusher_name,
                "commit_message": event.commit_message,
                "status": event.status,
                "scan_triggered": event.scan_triggered,
                "received_at": event.received_at.isoformat() if event.received_at else None
            }
            for event in events
        ]
    }
