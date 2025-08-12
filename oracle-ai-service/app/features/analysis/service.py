import random
from datetime import datetime, timezone
from app.features.analysis.schemas import (
    SentimentAnalysisRequest,
    SentimentAnalysisResponse,
    EngagementScoringRequest,
    EngagementScoringResponse,
    AudienceSegmentationRequest,
    AudienceSegmentationResponse,
    BehavioralPatternRequest,
    BehavioralPatternResponse,
)
from app.schemas import messaging
from app.models.ai.sentiment import sentiment_model


def analyze_batch_sentiment(
    request: SentimentAnalysisRequest,
) -> SentimentAnalysisResponse:
    """
    Performs sentiment analysis on a batch of text data using a real AI model.
    """
    individual_results = []
    total_score = 0

    for item in request.text_data:
        prediction = sentiment_model(item.text)
        score = (
            prediction["score"]
            if prediction["label"] == "positive"
            else -prediction["score"]
        )
        total_score += score

    individual_results.append(
        SentimentAnalysisResponse.IndividualResult(
            id=item.id,
            sentiment=SentimentAnalysisResponse.SentimentResult(
                score=round(score, 4), label=prediction["label"]
            ),
        )
    )

    # Calculate overall sentiment
    overall_score = total_score / len(request.text_data) if request.text_data else 0
    overall_label = "neutral"
    if overall_score > 0.3:
        overall_label = "positive"
    elif overall_score < -0.3:
        overall_label = "negative"

    return SentimentAnalysisResponse(
        overall_sentiment=SentimentAnalysisResponse.SentimentResult(
            score=round(overall_score, 4), label=overall_label
        ),
        individual_results=individual_results,
    )


def analyze_single_message(
    message: messaging.ChatMessagePayload,
) -> messaging.SentimentScorePredictionPayload:
    """
    Performs sentiment analysis on a single, real-time chat message using a real AI model.
    """
    # --- REPLACE PLACEHOLDER WITH REAL MODEL ---
    prediction = sentiment_model.predict(message.text)
    score = (
        prediction["score"]
        if prediction["label"] == "positive"
        else -prediction["score"]
    )

    return messaging.SentimentScorePredictionPayload(
        sourceMessageId=message.messageId,
        eventId=message.eventId,
        sessionId=message.sessionId,
        sentiment=prediction["label"],
        score=score,
        confidence=prediction["score"],  # The model's score is its confidence
        timestamp=datetime.now(timezone.utc),
    )


def score_engagement(request: EngagementScoringRequest) -> EngagementScoringResponse:
    """Simulates calculating engagement scores for users."""
    scores = []
    for interaction_group in request.user_interactions:
        score = round(random.uniform(30.0, 99.0), 2)
        level = "medium"
        if score > 80:
            level = "high"
        elif score < 50:
            level = "low"

        scores.append(
            EngagementScoringResponse.UserScore(
                user_id=interaction_group.user_id,
                engagement_score=score,
                engagement_level=level,
            )
        )
    return EngagementScoringResponse(user_scores=scores)


def segment_audience(
    request: AudienceSegmentationRequest,
) -> AudienceSegmentationResponse:
    """Simulates segmenting an audience based on behavior."""
    segments = [
        AudienceSegmentationResponse.Segment(
            segment_id="seg_power_networker",
            segment_name="Power Networkers",
            description="Attendees with a high number of connections and chat activity.",
            size=int(request.attendee_count * 0.15),  # Assume 15%
        ),
        AudienceSegmentationResponse.Segment(
            segment_id="seg_passive_learner",
            segment_name="Passive Learners",
            description="Attendees who primarily join sessions but have low interaction rates.",
            size=int(request.attendee_count * 0.40),  # Assume 40%
        ),
    ]
    return AudienceSegmentationResponse(segments=segments)


def analyze_behavior(request: BehavioralPatternRequest) -> BehavioralPatternResponse:
    """Simulates identifying common user behavior patterns."""
    patterns = [
        BehavioralPatternResponse.Pattern(
            pattern_id="p_session_hopper",
            pattern_name="Session Hopper",
            frequency=0.25,  # 25% of users
        ),
        BehavioralPatternResponse.Pattern(
            pattern_id="p_qa_enthusiast",
            pattern_name="Q&A Enthusiast",
            frequency=0.10,  # 10% of users
        ),
    ]
    return BehavioralPatternResponse(common_patterns=patterns)
