"""
LLM Client for Anthropic Claude
Handles API communication with prompt caching support and circuit breaker protection
"""
import logging
import time
from typing import Dict, Any, Optional, List
import asyncio
from anthropic import AsyncAnthropic
from anthropic.types import Message

from app.core.config import get_settings
from app.core.circuit_breaker import (
    llm_circuit_breaker,
    CircuitBreakerError,
    CircuitState
)

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMClient:
    """
    Async client for Anthropic Claude API with prompt caching support and circuit breaker.

    Supports:
    - Claude Sonnet 4.5 (primary)
    - Claude Haiku (fallback)
    - Prompt caching for cost optimization
    - Circuit breaker for resilience
    """

    # Model identifiers
    SONNET_4_5 = "claude-sonnet-4-5-20250929"
    HAIKU = "claude-haiku-4-5-20251001"

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize LLM client.

        Args:
            api_key: Anthropic API key (uses settings if not provided)
        """
        self.api_key = api_key or settings.ANTHROPIC_API_KEY
        if not self.api_key:
            logger.warning("No Anthropic API key configured - LLM features will be disabled")
            self.client = None
        else:
            self.client = AsyncAnthropic(api_key=self.api_key)

        self._circuit_breaker = llm_circuit_breaker
        self.logger = logging.getLogger(__name__)

    @property
    def circuit_state(self) -> CircuitState:
        """Get current circuit breaker state"""
        return self._circuit_breaker.state

    @property
    def circuit_breaker_stats(self) -> Dict:
        """Get circuit breaker statistics"""
        return self._circuit_breaker.stats.to_dict()

    def is_available(self) -> bool:
        """Check if LLM client is available (API key present and circuit not open)"""
        if not self.client:
            return False
        return self._circuit_breaker.state != CircuitState.OPEN

    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model: str = SONNET_4_5,
        max_tokens: int = 500,
        temperature: float = 0.7,
        use_cache: bool = True,
        timeout: float = 10.0
    ) -> Dict[str, Any]:
        """
        Generate text using Claude with prompt caching and circuit breaker protection.

        Args:
            system_prompt: System instructions (will be cached)
            user_prompt: User query (not cached)
            model: Model to use (SONNET_4_5 or HAIKU)
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-1)
            use_cache: Whether to use prompt caching
            timeout: Request timeout in seconds

        Returns:
            Dict with:
                - text: Generated text
                - model: Model used
                - tokens_input: Input tokens used
                - tokens_output: Output tokens generated
                - tokens_cache_read: Cached tokens read (if cache hit)
                - tokens_cache_write: Tokens written to cache
                - latency_ms: Generation latency

        Raises:
            CircuitBreakerError: If circuit breaker is open (service unhealthy)
            TimeoutError: If request times out
            Exception: For other API errors
        """
        if not self.client:
            raise Exception("LLM client not initialized - API key missing")

        start_time = time.time()

        try:
            # Circuit breaker wraps the entire API call
            async with self._circuit_breaker:
                # Build messages with prompt caching
                system_messages = []

                if use_cache:
                    # Mark system prompt for caching
                    system_messages.append({
                        "type": "text",
                        "text": system_prompt,
                        "cache_control": {"type": "ephemeral"}
                    })
                else:
                    system_messages.append({
                        "type": "text",
                        "text": system_prompt
                    })

                # Call Claude API with timeout
                response: Message = await asyncio.wait_for(
                    self.client.messages.create(
                        model=model,
                        max_tokens=max_tokens,
                        temperature=temperature,
                        system=system_messages,
                        messages=[
                            {
                                "role": "user",
                                "content": user_prompt
                            }
                        ]
                    ),
                    timeout=timeout
                )

            latency_ms = (time.time() - start_time) * 1000

            # Extract text from response
            text = ""
            for block in response.content:
                if block.type == "text":
                    text += block.text

            # Extract token usage
            usage = response.usage
            tokens_input = usage.input_tokens
            tokens_output = usage.output_tokens
            tokens_cache_read = getattr(usage, 'cache_read_input_tokens', 0)
            tokens_cache_write = getattr(usage, 'cache_creation_input_tokens', 0)

            result = {
                'text': text,
                'model': model,
                'tokens_input': tokens_input,
                'tokens_output': tokens_output,
                'tokens_cache_read': tokens_cache_read,
                'tokens_cache_write': tokens_cache_write,
                'latency_ms': latency_ms,
                'success': True
            }

            self.logger.info(
                f"✅ LLM generation successful: {model} - {latency_ms:.0f}ms - "
                f"Tokens: {tokens_input}in/{tokens_output}out "
                f"(cache: {tokens_cache_read}read/{tokens_cache_write}write)"
            )

            return result

        except CircuitBreakerError as e:
            latency_ms = (time.time() - start_time) * 1000
            self.logger.warning(f"⚡ LLM circuit breaker open: {e} ({latency_ms:.0f}ms)")
            raise

        except asyncio.TimeoutError:
            latency_ms = (time.time() - start_time) * 1000
            self.logger.error(f"⏱️ LLM timeout after {latency_ms:.0f}ms: {model}")
            raise TimeoutError(f"LLM generation timed out after {timeout}s")

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            self.logger.error(f"❌ LLM generation failed: {model} - {e}", exc_info=True)
            raise

    async def generate_with_fallback(
        self,
        system_prompt: str,
        user_prompt: str,
        primary_model: str = SONNET_4_5,
        fallback_model: str = HAIKU,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate with automatic fallback to faster model.

        Tries primary model first, falls back to fallback model if timeout/error.
        Circuit breaker errors trigger immediate fallback without counting against
        the circuit breaker.

        Args:
            system_prompt: System instructions
            user_prompt: User query
            primary_model: Primary model to try (default: Sonnet 4.5)
            fallback_model: Fallback model (default: Haiku)
            **kwargs: Additional arguments for generate()

        Returns:
            Generation result with 'fallback_used' flag
        """
        # Try primary model
        try:
            result = await self.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=primary_model,
                **kwargs
            )
            result['fallback_used'] = False
            return result

        except CircuitBreakerError as e:
            # Circuit is open - fail fast and try fallback
            self.logger.warning(f"Circuit breaker open for primary model, trying fallback {fallback_model}")

            # Try fallback model (circuit breaker allows limited requests in half-open)
            fallback_timeout = kwargs.get('timeout', 10.0) * 0.6
            kwargs['timeout'] = fallback_timeout

            result = await self.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=fallback_model,
                **kwargs
            )
            result['fallback_used'] = True
            result['fallback_reason'] = f"Circuit breaker open: {e}"
            return result

        except (TimeoutError, Exception) as e:
            self.logger.warning(f"Primary model failed: {e}, trying fallback {fallback_model}")

            # Try fallback model with shorter timeout
            fallback_timeout = kwargs.get('timeout', 10.0) * 0.6  # 60% of original timeout
            kwargs['timeout'] = fallback_timeout

            result = await self.generate(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=fallback_model,
                **kwargs
            )
            result['fallback_used'] = True
            result['fallback_reason'] = str(e)
            return result


# Global instance
llm_client = LLMClient()
