# =============================================================================
# Stripe Integration - Payments & Subscriptions
# =============================================================================
# Handles checkout sessions, subscriptions, and webhooks
# =============================================================================

from fastapi import APIRouter, HTTPException, status, Request, Depends
from pydantic import BaseModel
import stripe
import structlog

from core.config import settings
from core.clerk_auth import get_current_user

logger = structlog.get_logger()
router = APIRouter()

# Initialize Stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

# Pricing tiers
PRICING_TIERS = {
    "starter": {
        "name": "Starter",
        "price_monthly": 49,
        "price_yearly": 490,
        "stripe_price_id_monthly": "price_starter_monthly",  # Replace with actual Stripe IDs
        "stripe_price_id_yearly": "price_starter_yearly",
        "features": ["10 repos", "100 scans/month", "Email support"],
    },
    "pro": {
        "name": "Professional",
        "price_monthly": 149,
        "price_yearly": 1490,
        "stripe_price_id_monthly": "price_pro_monthly",
        "stripe_price_id_yearly": "price_pro_yearly",
        "features": ["Unlimited repos", "Unlimited scans", "Priority support", "Custom rules"],
    },
    "enterprise": {
        "name": "Enterprise",
        "price_monthly": None,  # Contact sales
        "price_yearly": None,
        "stripe_price_id_monthly": None,
        "stripe_price_id_yearly": None,
        "features": ["Everything in Pro", "SSO", "SLA", "Dedicated support"],
    },
}

class CreateCheckoutSessionRequest(BaseModel):
    tier: str  # starter, pro, enterprise
    billing_cycle: str  # monthly, yearly
    success_url: str
    cancel_url: str

class SubscriptionResponse(BaseModel):
    id: str
    status: str
    tier: str
    current_period_end: int
    cancel_at_period_end: bool

@router.get("/pricing")
async def get_pricing():
    """Get available pricing tiers."""
    return {
        "tiers": PRICING_TIERS,
        "currency": "usd"
    }

@router.post("/checkout-session")
async def create_checkout_session(
    request: CreateCheckoutSessionRequest,
    user: User = Depends(get_current_user)
):
    """Create a Stripe checkout session for subscription."""
    tier = PRICING_TIERS.get(request.tier)
    if not tier:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid pricing tier"
        )
    
    # Enterprise tier requires contact sales
    if request.tier == "enterprise":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Enterprise tier requires contacting sales"
        )
    
    price_id = (
        tier["stripe_price_id_monthly"] 
        if request.billing_cycle == "monthly" 
        else tier["stripe_price_id_yearly"]
    )
    
    try:
        checkout_session = stripe.checkout.Session.create(
            customer_email=user.email,
            line_items=[
                {
                    "price": price_id,
                    "quantity": 1,
                },
            ],
            mode="subscription",
            success_url=request.success_url,
            cancel_url=request.cancel_url,
            metadata={
                "user_id": str(user.id),
                "tier": request.tier,
            },
            subscription_data={
                "metadata": {
                    "user_id": str(user.id),
                    "tier": request.tier,
                }
            }
        )
        
        logger.info("Checkout session created", 
                   session_id=checkout_session.id, 
                   user_id=user.id,
                   tier=request.tier)
        
        return {"checkout_url": checkout_session.url}
        
    except stripe.error.StripeError as e:
        logger.error("Stripe error creating checkout session", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create checkout session"
        )

@router.get("/subscription")
async def get_subscription(user: User = Depends(get_current_user)):
    """Get current user's subscription."""
    # Query database for user's subscription
    # This is a placeholder - implement actual DB query
    return {
        "tier": "free",
        "status": "active",
        "features": ["5 repos", "20 scans/month"],
    }

@router.post("/portal-session")
async def create_portal_session(
    request: Request,
    user: User = Depends(get_current_user)
):
    """Create Stripe Customer Portal session for managing subscription."""
    data = await request.json()
    return_url = data.get("return_url", settings.FRONTEND_URL)
    
    # Get customer's Stripe ID from database
    # This is a placeholder
    stripe_customer_id = None
    
    if not stripe_customer_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active subscription found"
        )
    
    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=stripe_customer_id,
            return_url=return_url,
        )
        return {"portal_url": portal_session.url}
    except stripe.error.StripeError as e:
        logger.error("Stripe error creating portal session", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create portal session"
        )

@router.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhooks for subscription events."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    
    logger.info("Stripe webhook received", event_type=event["type"])
    
    # Handle specific events
    if event["type"] == "checkout.session.completed":
        await handle_checkout_completed(event["data"]["object"])
    elif event["type"] == "invoice.payment_succeeded":
        await handle_payment_succeeded(event["data"]["object"])
    elif event["type"] == "invoice.payment_failed":
        await handle_payment_failed(event["data"]["object"])
    elif event["type"] == "customer.subscription.deleted":
        await handle_subscription_deleted(event["data"]["object"])
    
    return {"status": "success"}

async def handle_checkout_completed(session: dict):
    """Handle successful checkout completion."""
    user_id = session.get("metadata", {}).get("user_id")
    tier = session.get("metadata", {}).get("tier")
    
    logger.info("Checkout completed", user_id=user_id, tier=tier)
    
    # Update user subscription in database
    # Send welcome email
    # Enable premium features

async def handle_payment_succeeded(invoice: dict):
    """Handle successful payment."""
    logger.info("Payment succeeded", invoice_id=invoice["id"])
    # Update subscription status
    # Send receipt email

async def handle_payment_failed(invoice: dict):
    """Handle failed payment."""
    logger.warning("Payment failed", invoice_id=invoice["id"])
    # Send payment failure email
    # Update subscription status to past_due

async def handle_subscription_deleted(subscription: dict):
    """Handle subscription cancellation."""
    logger.info("Subscription cancelled", subscription_id=subscription["id"])
    # Downgrade user to free tier
    # Send cancellation email
