# =============================================================================
# Clerk Webhook Handler
# =============================================================================
# Handles Clerk user events: created, updated, deleted
# =============================================================================

from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import JSONResponse
import svix
import structlog

from core.config import settings
from core.database import get_db
from models import User

logger = structlog.get_logger()
router = APIRouter()

async def verify_clerk_webhook(request: Request) -> dict:
    """Verify Clerk webhook signature."""
    if not settings.CLERK_WEBHOOK_SECRET:
        logger.error("CLERK_WEBHOOK_SECRET not configured")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Webhook secret not configured"
        )
    
    headers = request.headers
    payload = await request.body()
    
    try:
        wh = svix.Webhook(settings.CLERK_WEBHOOK_SECRET)
        event = wh.verify(payload, {
            "svix-id": headers.get("svix-id"),
            "svix-timestamp": headers.get("svix-timestamp"),
            "svix-signature": headers.get("svix-signature"),
        })
        return event
    except svix.exceptions.WebhookVerificationError as e:
        logger.warning("Invalid webhook signature", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )

@router.post("/clerk", status_code=status.HTTP_200_OK)
async def clerk_webhook(request: Request):
    """Handle Clerk webhook events."""
    event = await verify_clerk_webhook(request)
    
    event_type = event.get("type")
    data = event.get("data", {})
    
    logger.info("Clerk webhook received", event_type=event_type, user_id=data.get("id"))
    
    db_gen = get_db()
    db = await anext(db_gen)
    
    try:
        if event_type == "user.created":
            await handle_user_created(data, db)
        elif event_type == "user.updated":
            await handle_user_updated(data, db)
        elif event_type == "user.deleted":
            await handle_user_deleted(data, db)
        elif event_type == "session.created":
            await handle_session_created(data, db)
        else:
            logger.info("Unhandled Clerk event", event_type=event_type)
        
        return JSONResponse({"status": "ok"})
        
    except Exception as e:
        logger.error("Webhook handler failed", error=str(e), event_type=event_type)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook"
        )
    finally:
        await db_gen.aclose()

async def handle_user_created(data: dict, db):
    """Handle user.created event from Clerk."""
    from sqlalchemy import select
    
    clerk_id = data.get("id")
    email = data.get("email_addresses", [{}])[0].get("email_address") if data.get("email_addresses") else None
    
    if not email:
        logger.warning("User created without email", clerk_id=clerk_id)
        return
    
    # Check if user already exists
    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    
    if existing:
        # Link existing user to Clerk
        existing.clerk_id = clerk_id
        existing.name = data.get("first_name", "") + " " + data.get("last_name", "")
        existing.avatar_url = data.get("image_url")
        await db.commit()
        logger.info("Linked existing user to Clerk", user_id=existing.id, clerk_id=clerk_id)
        return
    
    # Create new user
    user = User(
        clerk_id=clerk_id,
        email=email,
        name=data.get("first_name", "") + " " + data.get("last_name", ""),
        avatar_url=data.get("image_url"),
        is_active=True
    )
    db.add(user)
    await db.commit()
    logger.info("Created new user from Clerk webhook", user_id=user.id, email=email)

async def handle_user_updated(data: dict, db):
    """Handle user.updated event from Clerk."""
    from sqlalchemy import select
    
    clerk_id = data.get("id")
    
    result = await db.execute(select(User).where(User.clerk_id == clerk_id))
    user = result.scalar_one_or_none()
    
    if not user:
        logger.warning("User update received but user not found", clerk_id=clerk_id)
        return
    
    # Update user fields
    email = data.get("email_addresses", [{}])[0].get("email_address") if data.get("email_addresses") else None
    if email:
        user.email = email
    
    user.name = data.get("first_name", "") + " " + data.get("last_name", "")
    user.avatar_url = data.get("image_url")
    user.is_active = not data.get("banned", False)
    
    await db.commit()
    logger.info("Updated user from Clerk webhook", user_id=user.id, clerk_id=clerk_id)

async def handle_user_deleted(data: dict, db):
    """Handle user.deleted event from Clerk."""
    from sqlalchemy import select
    
    clerk_id = data.get("id")
    
    result = await db.execute(select(User).where(User.clerk_id == clerk_id))
    user = result.scalar_one_or_none()
    
    if user:
        # Soft delete - mark as inactive
        user.is_active = False
        await db.commit()
        logger.info("Deactivated user from Clerk webhook", user_id=user.id, clerk_id=clerk_id)
    else:
        logger.warning("User delete received but user not found", clerk_id=clerk_id)

async def handle_session_created(data: dict, db):
    """Handle session.created event for analytics."""
    user_id = data.get("user_id")
    logger.info("User session created", clerk_user_id=user_id)
    # Can be used for login analytics, last seen tracking, etc.
