import stripe
import logging
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import User, SubscriptionTier
from app.settings import config
import datetime

logger = logging.getLogger(__name__)

# Set Stripe API key
stripe.api_key = config.STRIPE_SECRET_KEY

router = APIRouter(
    prefix="/stripe",
    tags=["stripe-webhooks"]
)

@router.post("/webhook")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    """Handle Stripe webhook events for subscription management"""
    
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        # Verify webhook signature
        event = stripe.Webhook.construct_event(
            payload, sig_header, config.STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        logger.error("Invalid payload in Stripe webhook")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        logger.error("Invalid signature in Stripe webhook")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the event
    if event['type'] == 'customer.subscription.created':
        await handle_subscription_created(event['data']['object'], db)
    elif event['type'] == 'customer.subscription.updated':
        await handle_subscription_updated(event['data']['object'], db)
    elif event['type'] == 'customer.subscription.deleted':
        await handle_subscription_deleted(event['data']['object'], db)
    elif event['type'] == 'invoice.payment_succeeded':
        await handle_payment_succeeded(event['data']['object'], db)
    elif event['type'] == 'invoice.payment_failed':
        await handle_payment_failed(event['data']['object'], db)
    else:
        logger.info(f"Unhandled event type: {event['type']}")

    return {"status": "success"}

async def handle_subscription_created(subscription, db: Session):
    """Handle new subscription creation"""
    customer_id = subscription['customer']
    subscription_id = subscription['id']
    
    # Get customer email from Stripe
    customer = stripe.Customer.retrieve(customer_id)
    customer_email = customer.email
    
    # Find user by email
    user = db.query(User).filter(User.email == customer_email).first()
    if not user:
        logger.error(f"User not found for email {customer_email}")
        return
    
    # Update user subscription
    user.stripe_customer_id = customer_id
    user.stripe_subscription_id = subscription_id
    user.subscription_status = subscription['status']
    user.subscription_tier = SubscriptionTier.PRO
    user.subscription_current_period_end = datetime.datetime.fromtimestamp(
        subscription['current_period_end'], tz=datetime.timezone.utc
    )
    
    db.commit()
    logger.info(f"Activated Pro subscription for user {user.email}")

async def handle_subscription_updated(subscription, db: Session):
    """Handle subscription updates (renewals, plan changes)"""
    subscription_id = subscription['id']
    
    user = db.query(User).filter(User.stripe_subscription_id == subscription_id).first()
    if not user:
        logger.error(f"User not found for subscription {subscription_id}")
        return
    
    # Update subscription status
    user.subscription_status = subscription['status']
    user.subscription_current_period_end = datetime.datetime.fromtimestamp(
        subscription['current_period_end'], tz=datetime.timezone.utc
    )
    
    # Handle subscription status changes
    if subscription['status'] == 'active':
        user.subscription_tier = SubscriptionTier.PRO
    elif subscription['status'] in ['canceled', 'past_due', 'unpaid']:
        user.subscription_tier = SubscriptionTier.FREE
    
    db.commit()
    logger.info(f"Updated subscription for user {user.email}: {subscription['status']}")

async def handle_subscription_deleted(subscription, db: Session):
    """Handle subscription cancellation"""
    subscription_id = subscription['id']
    
    user = db.query(User).filter(User.stripe_subscription_id == subscription_id).first()
    if not user:
        logger.error(f"User not found for subscription {subscription_id}")
        return
    
    # Downgrade to free tier
    user.subscription_tier = SubscriptionTier.FREE
    user.subscription_status = 'canceled'
    user.stripe_subscription_id = None
    
    db.commit()
    logger.info(f"Downgraded user {user.email} to free tier")

async def handle_payment_succeeded(invoice, db: Session):
    """Handle successful payment"""
    customer_id = invoice['customer']
    
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return
    
    # Ensure user is on Pro tier if payment succeeded
    if user.subscription_status == 'active':
        user.subscription_tier = SubscriptionTier.PRO
        db.commit()
        logger.info(f"Payment succeeded for user {user.email}")

async def handle_payment_failed(invoice, db: Session):
    """Handle failed payment"""
    customer_id = invoice['customer']
    
    user = db.query(User).filter(User.stripe_customer_id == customer_id).first()
    if not user:
        return
    
    logger.warning(f"Payment failed for user {user.email}")
    # Note: Don't immediately downgrade - Stripe will retry 