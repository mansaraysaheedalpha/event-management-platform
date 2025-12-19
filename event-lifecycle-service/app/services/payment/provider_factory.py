# app/services/payment/provider_factory.py
import os
import logging
from typing import Dict, Optional, List
from dataclasses import dataclass
from functools import lru_cache

from app.core.config import settings
from .provider_interface import PaymentProviderInterface, PaymentFeature
from .providers.stripe_provider import StripeProvider, StripeConfig

logger = logging.getLogger(__name__)


@dataclass
class ProviderSelectionContext:
    """Context for selecting the appropriate payment provider."""
    currency: str
    country: Optional[str] = None
    amount: int = 0
    organization_id: Optional[str] = None


@dataclass
class ProviderInfo:
    """Information about an available payment provider."""
    code: str
    name: str
    supported_currencies: List[str]
    supported_countries: List[str]
    features: List[PaymentFeature]
    is_active: bool


# Currency to provider routing configuration
PROVIDER_ROUTING: Dict[str, str] = {
    # Stripe-supported currencies
    "USD": "stripe",
    "EUR": "stripe",
    "GBP": "stripe",
    "CAD": "stripe",
    "AUD": "stripe",
    "JPY": "stripe",
    "CHF": "stripe",
    "DKK": "stripe",
    "NOK": "stripe",
    "SEK": "stripe",
    "SGD": "stripe",
    "HKD": "stripe",
    "NZD": "stripe",
    # Future: African providers
    # "NGN": "paystack",
    # "GHS": "paystack",
    # "KES": "flutterwave",
}

DEFAULT_PROVIDER = "stripe"


class PaymentProviderFactory:
    """
    Factory for creating and managing payment provider instances.

    Supports multiple providers and routing based on currency/region.
    """

    def __init__(self):
        self._providers: Dict[str, PaymentProviderInterface] = {}
        self._initialize_providers()

    def _initialize_providers(self) -> None:
        """Initialize all configured payment providers."""
        # Initialize Stripe if configured
        stripe_secret_key = settings.STRIPE_SECRET_KEY
        stripe_publishable_key = settings.STRIPE_PUBLISHABLE_KEY
        stripe_webhook_secret = settings.STRIPE_WEBHOOK_SECRET

        if stripe_secret_key and stripe_publishable_key and stripe_webhook_secret:
            config = StripeConfig(
                secret_key=stripe_secret_key,
                publishable_key=stripe_publishable_key,
                webhook_secret=stripe_webhook_secret,
                api_version=os.getenv("STRIPE_API_VERSION", "2023-10-16"),
                max_retries=int(os.getenv("STRIPE_MAX_NETWORK_RETRIES", "2")),
            )
            self._providers["stripe"] = StripeProvider(config)
            logger.info("Stripe payment provider initialized")
        else:
            logger.warning(
                "Stripe provider not initialized: missing environment variables"
            )

        # Future: Initialize other providers (Paystack, Flutterwave, etc.)

    def get_provider(self, code: str) -> PaymentProviderInterface:
        """
        Get a payment provider by its code.

        Args:
            code: Provider code (e.g., 'stripe', 'paystack')

        Returns:
            PaymentProviderInterface instance

        Raises:
            ValueError: If provider is not available
        """
        provider = self._providers.get(code)
        if not provider:
            raise ValueError(f"Payment provider '{code}' is not available")
        return provider

    def get_provider_for_context(
        self, context: ProviderSelectionContext
    ) -> PaymentProviderInterface:
        """
        Get the appropriate provider for a given context.

        Selection logic:
        1. Organization's configured provider (if set) - TODO: implement
        2. Currency/region mapping
        3. Fallback to default provider

        Args:
            context: Provider selection context

        Returns:
            PaymentProviderInterface instance
        """
        # TODO: Check organization's configured provider first
        # org_settings = get_org_payment_settings(context.organization_id)
        # if org_settings and org_settings.provider_code:
        #     return self.get_provider(org_settings.provider_code)

        # Route by currency
        provider_code = PROVIDER_ROUTING.get(
            context.currency.upper(), DEFAULT_PROVIDER
        )

        try:
            return self.get_provider(provider_code)
        except ValueError:
            # Fall back to default
            return self.get_provider(DEFAULT_PROVIDER)

    def get_default_provider(self) -> PaymentProviderInterface:
        """Get the default payment provider."""
        return self.get_provider(DEFAULT_PROVIDER)

    def list_available_providers(self) -> List[ProviderInfo]:
        """List all available payment providers with their capabilities."""
        providers = []
        for code, provider in self._providers.items():
            features = [f for f in PaymentFeature if provider.supports_feature(f)]
            providers.append(
                ProviderInfo(
                    code=provider.code,
                    name=provider.name,
                    supported_currencies=list(
                        k for k, v in PROVIDER_ROUTING.items() if v == code
                    ),
                    supported_countries=[],  # TODO: Populate from provider
                    features=features,
                    is_active=True,
                )
            )
        return providers

    def is_provider_available(
        self, code: str, context: Optional[ProviderSelectionContext] = None
    ) -> bool:
        """
        Check if a provider is available for use.

        Args:
            code: Provider code
            context: Optional context for additional validation

        Returns:
            True if provider is available
        """
        if code not in self._providers:
            return False

        if context:
            # Check if provider supports the currency
            expected_provider = PROVIDER_ROUTING.get(context.currency.upper())
            if expected_provider and expected_provider != code:
                return False

        return True


# Global factory instance (singleton pattern)
_factory_instance: Optional[PaymentProviderFactory] = None


def get_payment_provider_factory() -> PaymentProviderFactory:
    """Get the global payment provider factory instance."""
    global _factory_instance
    if _factory_instance is None:
        _factory_instance = PaymentProviderFactory()
    return _factory_instance


def get_payment_provider(code: str = "stripe") -> PaymentProviderInterface:
    """
    Convenience function to get a payment provider by code.

    Args:
        code: Provider code (default: 'stripe')

    Returns:
        PaymentProviderInterface instance
    """
    factory = get_payment_provider_factory()
    return factory.get_provider(code)


def get_provider_for_currency(currency: str) -> PaymentProviderInterface:
    """
    Get the appropriate payment provider for a currency.

    Args:
        currency: ISO 4217 currency code

    Returns:
        PaymentProviderInterface instance
    """
    factory = get_payment_provider_factory()
    context = ProviderSelectionContext(currency=currency)
    return factory.get_provider_for_context(context)
