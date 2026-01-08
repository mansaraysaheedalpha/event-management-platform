# app/models/__init__.py
# Import all models to ensure SQLAlchemy can resolve relationships
# Order matters for dependencies - import base models first

from app.db.base_class import Base
from app.models.event import Event
from app.models.venue import Venue
from app.models.speaker import Speaker
from app.models.session import Session
from app.models.session_speaker import session_speaker_association
from app.models.session_capacity import SessionCapacity
from app.models.session_waitlist import SessionWaitlist, WaitlistEvent
from app.models.presentation import Presentation
from app.models.registration import Registration
from app.models.waitlist import WaitlistEntry
from app.models.waitlist_analytics import WaitlistAnalytics
from app.models.domain_event import DomainEvent
from app.models.blueprint import EventBlueprint

# Payment models
from app.models.payment_provider import PaymentProvider
from app.models.organization_payment_settings import OrganizationPaymentSettings
from app.models.payment import Payment
from app.models.refund import Refund
from app.models.payment_webhook_event import PaymentWebhookEvent
from app.models.payment_audit_log import PaymentAuditLog

# Ticketing models - order matters for relationships
from app.models.ticket_type import TicketType
from app.models.order import Order
from app.models.order_item import OrderItem
from app.models.ticket import Ticket
from app.models.promo_code import PromoCode
from app.models.promo_code_usage import PromoCodeUsage

# Monetization models
from app.models.offer import Offer
from app.models.offer_purchase import OfferPurchase
from app.models.ad import Ad
from app.models.ad_event import AdEvent
from app.models.monetization_event import MonetizationEvent
from app.models.ab_test import ABTest, ABTestEvent

__all__ = [
    "Base",
    "Event",
    "Venue",
    "Speaker",
    "Session",
    "session_speaker_association",
    "SessionCapacity",
    "SessionWaitlist",
    "WaitlistEvent",
    "Presentation",
    "Registration",
    "WaitlistEntry",
    "WaitlistAnalytics",
    "DomainEvent",
    "EventBlueprint",
    "PaymentProvider",
    "OrganizationPaymentSettings",
    "Payment",
    "Refund",
    "PaymentWebhookEvent",
    "PaymentAuditLog",
    "TicketType",
    "Order",
    "OrderItem",
    "Ticket",
    "PromoCode",
    "PromoCodeUsage",
    "Offer",
    "OfferPurchase",
    "Ad",
    "AdEvent",
    "MonetizationEvent",
    "ABTest",
    "ABTestEvent",
]
