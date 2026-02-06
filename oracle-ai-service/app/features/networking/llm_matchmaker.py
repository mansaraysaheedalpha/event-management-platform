# app/features/networking/llm_matchmaker.py
"""
LLM-powered networking matchmaking using Anthropic Claude.
Provides intelligent matching based on semantic understanding of profiles,
goals compatibility, and skills complementarity.
"""

import json
import logging
from typing import List, Optional

from anthropic import AsyncAnthropic

from app.core.config import settings
from app.core.circuit_breaker import get_anthropic_breaker
from app.core.exceptions import CircuitBreakerOpenError
from app.core.rate_limiter import get_llm_limiter

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"


def _build_user_summary(user) -> str:
    """Build a concise text summary of a user profile for the LLM prompt."""
    parts = [f"ID: {user.user_id}"]
    if user.name:
        parts.append(f"Name: {user.name}")
    if user.role and user.company:
        parts.append(f"Role: {user.role} at {user.company}")
    elif user.role:
        parts.append(f"Role: {user.role}")
    elif user.company:
        parts.append(f"Company: {user.company}")
    if user.industry:
        parts.append(f"Industry: {user.industry}")
    if user.headline:
        parts.append(f"Headline: {user.headline}")
    if user.interests:
        parts.append(f"Interests: {', '.join(user.interests)}")
    if user.goals:
        parts.append(f"Goals: {', '.join(user.goals)}")
    if user.skills_to_offer:
        parts.append(f"Skills to offer: {', '.join(user.skills_to_offer)}")
    if user.skills_needed:
        parts.append(f"Looking for: {', '.join(user.skills_needed)}")
    if user.bio:
        parts.append(f"Bio: {user.bio[:200]}")
    return "\n  ".join(parts)


async def llm_rank_matches(
    primary_user,
    candidates: list,
    max_matches: int = 10,
) -> Optional[List[dict]]:
    """
    Use Claude to intelligently rank networking matches.

    Args:
        primary_user: The user seeking matches (MatchmakingRequest.UserProfile)
        candidates: Pre-filtered candidate profiles
        max_matches: Maximum matches to return

    Returns:
        List of match dicts with user_id, match_score, common_interests, match_reasons
        or None if LLM call fails
    """
    if not settings.ANTHROPIC_API_KEY:
        logger.debug("No ANTHROPIC_API_KEY, skipping LLM matching")
        return None

    # Build candidate summaries (limit to 20 to keep prompt reasonable)
    candidate_summaries = []
    for c in candidates[:20]:
        candidate_summaries.append(f"- {_build_user_summary(c)}")

    if not candidate_summaries:
        return None

    prompt = f"""You are an AI networking matchmaker at a professional event. Analyze the primary user's profile and rank the best networking matches from the candidates.

PRIMARY USER:
  {_build_user_summary(primary_user)}

CANDIDATES:
{chr(10).join(candidate_summaries)}

Rank the top {max_matches} best matches. Consider:
1. Complementary goals (e.g., someone looking to hire matches with someone seeking a job)
2. Skills exchange potential (one offers what the other needs)
3. Semantic interest overlap (e.g., "AI/ML" and "Machine Learning" are related)
4. Industry relevance and professional synergy
5. Potential for meaningful collaboration

Return ONLY a JSON array (no markdown, no explanation) with this structure:
[
  {{
    "user_id": "the candidate's ID",
    "match_score": 0.85,
    "common_interests": ["semantically shared interests"],
    "match_reasons": ["Specific reason why they should connect", "Another reason"]
  }}
]

Rules:
- match_score: 0.0 to 1.0 (be realistic, not everyone is a great match)
- common_interests: include semantically related interests, not just exact matches
- match_reasons: 1-3 specific, actionable reasons (not generic like "shared interests")
- Only include candidates worth connecting with (score > 0.3)
- Sort by match_score descending"""

    try:
        limiter = await get_llm_limiter()
        await limiter.acquire()

        breaker = get_anthropic_breaker()

        async with breaker:
            client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            response = await client.messages.create(
                model=MODEL,
                max_tokens=2000,
                messages=[{"role": "user", "content": prompt}],
            )

            text = response.content[0].text.strip()

            # Extract JSON from response
            json_str = text
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0]

            matches = json.loads(json_str.strip())

            # Validate and cap scores
            valid_matches = []
            valid_candidate_ids = {c.user_id for c in candidates}
            for m in matches:
                if m.get("user_id") not in valid_candidate_ids:
                    continue
                valid_matches.append({
                    "user_id": m["user_id"],
                    "match_score": max(0.0, min(1.0, float(m.get("match_score", 0.5)))),
                    "common_interests": m.get("common_interests", []),
                    "match_reasons": m.get("match_reasons", ["Networking match"]),
                })

            logger.info(f"LLM ranked {len(valid_matches)} matches for user {primary_user.user_id}")
            return valid_matches[:max_matches]

    except CircuitBreakerOpenError:
        logger.warning("Anthropic circuit breaker open, skipping LLM matching")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM match response: {e}")
        return None
    except Exception as e:
        logger.error(f"LLM matchmaking failed: {e}")
        return None


async def llm_conversation_starters(
    user1_id: str,
    user2_id: str,
    common_interests: List[str],
    user1_name: Optional[str] = None,
    user1_role: Optional[str] = None,
    user1_company: Optional[str] = None,
    user1_bio: Optional[str] = None,
    user2_name: Optional[str] = None,
    user2_role: Optional[str] = None,
    user2_company: Optional[str] = None,
    user2_bio: Optional[str] = None,
    match_reasons: Optional[List[str]] = None,
) -> Optional[List[str]]:
    """
    Use Claude to generate personalized conversation starters.

    Returns:
        List of 2-3 conversation starter strings, or None if LLM fails
    """
    if not settings.ANTHROPIC_API_KEY:
        return None

    # Build user context
    user1_parts = [f"ID: {user1_id}"]
    if user1_name:
        user1_parts.append(f"Name: {user1_name}")
    if user1_role:
        user1_parts.append(f"Role: {user1_role}")
    if user1_company:
        user1_parts.append(f"Company: {user1_company}")
    if user1_bio:
        user1_parts.append(f"Bio: {user1_bio[:150]}")

    user2_parts = [f"ID: {user2_id}"]
    if user2_name:
        user2_parts.append(f"Name: {user2_name}")
    if user2_role:
        user2_parts.append(f"Role: {user2_role}")
    if user2_company:
        user2_parts.append(f"Company: {user2_company}")
    if user2_bio:
        user2_parts.append(f"Bio: {user2_bio[:150]}")

    interests_str = ", ".join(common_interests) if common_interests else "None identified"
    reasons_str = "; ".join(match_reasons) if match_reasons else "General networking"

    prompt = f"""Generate 2-3 natural conversation starters for User 1 to say to User 2 at a professional networking event.

USER 1: {', '.join(user1_parts)}
USER 2: {', '.join(user2_parts)}
SHARED INTERESTS: {interests_str}
WHY THEY MATCH: {reasons_str}

Rules:
- Be specific and reference actual profile details when available
- Sound natural, not robotic or templated
- Keep each starter to 1-2 sentences
- Make them open-ended to encourage conversation
- Don't use User 1's name in the starters (they're saying it themselves)
- Reference User 2's name naturally if available

Return ONLY a JSON array of strings (no markdown, no explanation):
["starter 1", "starter 2", "starter 3"]"""

    try:
        limiter = await get_llm_limiter()
        await limiter.acquire()

        breaker = get_anthropic_breaker()

        async with breaker:
            client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            response = await client.messages.create(
                model=MODEL,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}],
            )

            text = response.content[0].text.strip()

            json_str = text
            if "```json" in text:
                json_str = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                json_str = text.split("```")[1].split("```")[0]

            starters = json.loads(json_str.strip())

            if isinstance(starters, list) and all(isinstance(s, str) for s in starters):
                logger.info(f"LLM generated {len(starters)} conversation starters")
                return starters[:3]

            logger.warning("LLM returned unexpected format for conversation starters")
            return None

    except CircuitBreakerOpenError:
        logger.warning("Anthropic circuit breaker open, skipping LLM starters")
        return None
    except json.JSONDecodeError as e:
        logger.warning(f"Failed to parse LLM starter response: {e}")
        return None
    except Exception as e:
        logger.error(f"LLM conversation starters failed: {e}")
        return None
