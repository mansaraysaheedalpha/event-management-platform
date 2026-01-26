# app/services/ai_message_generator.py
"""
AI-powered message generation for sponsor campaigns using Claude API.

Features:
- Context-aware message generation based on event, sponsor, and audience
- Multiple tone options (professional, casual, friendly)
- Subject line and body generation
- Personalization variable suggestions
"""

import os
from typing import Optional, Dict, Any, List
from anthropic import Anthropic
import logging

logger = logging.getLogger(__name__)


class AIMessageGenerator:
    """Service for generating campaign messages using Claude AI."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the AI message generator."""
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY not configured. AI features will be disabled.")
            self.client = None
        else:
            self.client = Anthropic(api_key=self.api_key)

    def is_available(self) -> bool:
        """Check if AI generation is available."""
        return self.client is not None

    def generate_campaign_message(
        self,
        *,
        event_name: str,
        event_description: Optional[str] = None,
        sponsor_name: str,
        sponsor_description: Optional[str] = None,
        audience_type: str,
        campaign_goal: Optional[str] = None,
        tone: str = "professional",
        include_cta: bool = True,
        previous_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a personalized campaign message using Claude AI.

        Args:
            event_name: Name of the event
            event_description: Description of the event
            sponsor_name: Name of the sponsor company
            sponsor_description: What the sponsor does
            audience_type: Type of audience (hot, warm, cold, all)
            campaign_goal: What the sponsor wants to achieve (demo, follow-up, nurture, etc.)
            tone: Tone of the message (professional, casual, friendly)
            include_cta: Whether to include a call-to-action
            previous_context: Any previous interaction context

        Returns:
            dict with 'subject', 'body', 'suggestions', and 'reasoning'
        """
        if not self.is_available():
            raise ValueError("AI message generation is not available. Please configure ANTHROPIC_API_KEY.")

        # Build the prompt
        prompt = self._build_generation_prompt(
            event_name=event_name,
            event_description=event_description,
            sponsor_name=sponsor_name,
            sponsor_description=sponsor_description,
            audience_type=audience_type,
            campaign_goal=campaign_goal,
            tone=tone,
            include_cta=include_cta,
            previous_context=previous_context,
        )

        try:
            # Call Claude API
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=1500,
                temperature=0.7,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )

            # Parse the response
            content = response.content[0].text

            # Extract subject and body from the response
            result = self._parse_ai_response(content)

            return result

        except Exception as e:
            logger.error(f"AI message generation failed: {e}")
            raise

    def _build_generation_prompt(
        self,
        event_name: str,
        event_description: Optional[str],
        sponsor_name: str,
        sponsor_description: Optional[str],
        audience_type: str,
        campaign_goal: Optional[str],
        tone: str,
        include_cta: bool,
        previous_context: Optional[str],
    ) -> str:
        """Build the prompt for Claude AI."""

        # Map audience types to descriptions
        audience_descriptions = {
            "hot": "highly engaged leads who spent significant time at the booth, downloaded resources, and asked questions",
            "warm": "moderately engaged leads who visited the booth and showed some interest",
            "cold": "leads who briefly visited the booth with minimal engagement",
            "all": "all booth visitors regardless of engagement level",
            "new": "leads who have never been contacted before",
            "contacted": "leads who have been contacted previously",
        }

        audience_desc = audience_descriptions.get(audience_type, "booth visitors")

        prompt = f"""You are an expert email marketing copywriter specializing in B2B event follow-up campaigns. Generate a personalized follow-up email for a sponsor to send to their event leads.

**Context:**
- Event: {event_name}
{f"- Event Description: {event_description}" if event_description else ""}
- Sponsor Company: {sponsor_name}
{f"- About Sponsor: {sponsor_description}" if sponsor_description else ""}
- Target Audience: {audience_desc}
{f"- Campaign Goal: {campaign_goal}" if campaign_goal else "- Campaign Goal: Follow up with booth visitors and nurture the relationship"}
{f"- Previous Context: {previous_context}" if previous_context else ""}

**Requirements:**
- Tone: {tone} and personable
- Length: Keep the email concise (150-250 words max)
- Personalization: Use {{{{name}}}}, {{{{company}}}}, {{{{title}}}} template variables where appropriate
- Subject Line: Compelling and specific (not generic)
{f"- Call-to-Action: Include a clear next step" if include_cta else "- Call-to-Action: Soft close, no hard ask"}

**Output Format:**
Return your response in this exact format:

SUBJECT: [Your subject line here]

BODY:
[Your email body here]

REASONING:
[2-3 sentences explaining why this message will resonate with this audience]

SUGGESTIONS:
- [Tip 1 for improving engagement]
- [Tip 2 for improving engagement]

**Best Practices:**
1. Reference the event specifically
2. Make it feel personal, not automated
3. Focus on value to the recipient, not selling
4. Keep it conversational and human
5. Use the recipient's name and company in a natural way
6. Make the subject line curiosity-driven or benefit-focused

Generate the campaign message now:"""

        return prompt

    def _parse_ai_response(self, content: str) -> Dict[str, Any]:
        """Parse Claude's response into structured data."""

        lines = content.strip().split('\n')

        subject = ""
        body = ""
        reasoning = ""
        suggestions = []

        current_section = None

        for line in lines:
            line_stripped = line.strip()

            if line_stripped.startswith("SUBJECT:"):
                current_section = "subject"
                subject = line_stripped.replace("SUBJECT:", "").strip()
            elif line_stripped.startswith("BODY:"):
                current_section = "body"
            elif line_stripped.startswith("REASONING:"):
                current_section = "reasoning"
            elif line_stripped.startswith("SUGGESTIONS:"):
                current_section = "suggestions"
            elif current_section == "body" and line_stripped:
                body += line_stripped + "\n"
            elif current_section == "reasoning" and line_stripped:
                reasoning += line_stripped + " "
            elif current_section == "suggestions" and line_stripped.startswith("-"):
                suggestions.append(line_stripped[1:].strip())

        return {
            "subject": subject or "Follow-up from " + content.split('\n')[0][:50],
            "body": body.strip() or content[:500],
            "reasoning": reasoning.strip() or "AI-generated message based on your campaign context",
            "suggestions": suggestions or ["Test different subject lines", "Send at optimal times"],
        }

    def generate_subject_variations(
        self,
        base_subject: str,
        count: int = 3
    ) -> List[str]:
        """Generate variations of a subject line for A/B testing."""

        if not self.is_available():
            raise ValueError("AI generation not available")

        prompt = f"""Generate {count} variations of this email subject line for A/B testing.

Original: {base_subject}

Requirements:
- Keep the same core message and tone
- Vary the approach (question vs statement, curiosity vs benefit, etc.)
- Keep each under 60 characters
- Make them compelling and click-worthy

Return only the subject lines, one per line, without numbering or bullets."""

        try:
            response = self.client.messages.create(
                model="claude-sonnet-4-5-20250929",
                max_tokens=500,
                temperature=0.9,
                messages=[{"role": "user", "content": prompt}]
            )

            variations = [
                line.strip()
                for line in response.content[0].text.strip().split('\n')
                if line.strip()
            ]

            return variations[:count]

        except Exception as e:
            logger.error(f"Subject variation generation failed: {e}")
            return [base_subject]  # Fallback to original


# Singleton instance
ai_generator = AIMessageGenerator()
