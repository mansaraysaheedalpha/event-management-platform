# app/features/analysis/service.py
from typing import List
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
from collections import defaultdict
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


def analyze_batch_sentiment(
    request: SentimentAnalysisRequest,
) -> SentimentAnalysisResponse:
    """
    Performs sentiment analysis on a batch of text data using our robust model class.
    """
    individual_results = []
    total_score = 0

    # This logic remains largely the same, but now it calls our reliable `sentiment_model`
    for item in request.text_data:
        prediction = sentiment_model.predict(item.text)
        # Normalize score: positive score for "positive", negative for "negative"
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
    Performs sentiment analysis on a single, real-time chat message using our robust model class.
    """
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
        confidence=prediction["score"],  # The model's raw score is its confidence
        timestamp=datetime.now(timezone.utc),
    )


def score_engagement(request: EngagementScoringRequest) -> EngagementScoringResponse:
    """
    Calculates engagement scores for users based on a weighted, rules-based model.

    This is a world-class approach because it is:
    - **Explainable:** The business can easily understand and tweak the weights.
    - **Fast:** It's a simple calculation with no ML model overhead.
    - **Effective:** It provides a strong, quantifiable measure of user engagement.
    """
    # Define the weights for each interaction type. This can be moved to a
    # configuration file or a database table for even more flexibility.
    INTERACTION_WEIGHTS = {
        "click": 1,
        "document_download": 2,
        "poll_vote": 3,
        "question_upvote": 5,
        # 'scroll', 'view', etc., have a default weight of 0
    }

    # Use defaultdict to easily accumulate scores for each user
    user_scores_map = defaultdict(float)

    for interaction in request.user_interactions:
        score = INTERACTION_WEIGHTS.get(interaction.interaction_type, 0)
        user_scores_map[interaction.user_id] += score

    # Process the calculated scores into the final response objects
    final_scores = []
    for user_id, score in user_scores_map.items():
        if score == 0:
            continue  # Don't include users with a score of 0

        level = "low"
        if score > 7:
            level = "high"
        elif score > 3:
            level = "medium"

        final_scores.append(
            EngagementScoringResponse.UserScore(
                user_id=user_id,
                engagement_score=score,
                engagement_level=level,
            )
        )

    return EngagementScoringResponse(user_scores=final_scores)


def segment_audience(
    request: AudienceSegmentationRequest,
) -> AudienceSegmentationResponse:
    """
    Segments an audience using K-Means clustering on engagement scores.

    This is a world-class approach because it:
    - **Is Data-Driven:** The segments are discovered from the data itself,
      not based on arbitrary rules.
    - **Is Scalable:** K-Means is highly efficient and can handle tens of
      thousands of attendees with ease.
    - **Is Extensible:** We can easily add more features (e.g., sessions attended,
      messages sent) to create richer, multi-dimensional segments in the future.
    """
    if len(request.attendee_data) < 2:
        # Not enough data to form clusters
        return AudienceSegmentationResponse(segments=[])

    # 1. Prepare the data for machine learning
    # We create a mapping to link the array index back to the user_id
    index_to_user_id = {
        i: attendee["user_id"] for i, attendee in enumerate(request.attendee_data)
    }

    # Extract the engagement scores into a NumPy array
    feature_matrix = np.array(
        [attendee["engagement_score"] for attendee in request.attendee_data]
    ).reshape(-1, 1)

    # Scale the data - this is crucial for distance-based algorithms like K-Means
    scaler = StandardScaler()
    scaled_features = scaler.fit_transform(feature_matrix)

    # 2. Run the K-Means algorithm
    # We'll create 2 clusters for this example (e.g., low and high engagement)
    # This number of clusters ('k') can be determined dynamically in more advanced versions.
    kmeans = KMeans(n_clusters=2, random_state=42, n_init="auto")
    kmeans.fit(scaled_features)

    # 3. Process and name the resulting clusters
    clusters = defaultdict(list)
    for i, label in enumerate(kmeans.labels_):
        user_id = index_to_user_id[i]
        original_score = feature_matrix[i][0]
        clusters[label].append({"user_id": user_id, "score": original_score})

    # Assign meaningful names to the clusters based on their average score
    final_segments = []
    for label, members in clusters.items():
        avg_score = np.mean([m["score"] for m in members])

        segment_name = "Moderately Engaged"
        if avg_score > 75:
            segment_name = "High Engagement Superfans"
        elif avg_score < 25:
            segment_name = "Low Engagement Observers"

        final_segments.append(
            AudienceSegmentationResponse.Segment(
                segment_id=f"seg_{label}",
                segment_name=segment_name,
                description=f"A segment of users with an average engagement score of {int(avg_score)}.",
                size=len(members),
            )
        )

    return AudienceSegmentationResponse(segments=final_segments)


def analyze_behavior(request: BehavioralPatternRequest) -> BehavioralPatternResponse:
    """
    Analyzes user journeys to find common behavioral patterns using a Trie.

    This is a world-class approach because it is:
    - **Algorithmically Efficient:** Processes all journeys in a single pass.
    - **Memory Smart:** The Trie structure naturally compresses shared prefixes,
      saving memory on large datasets.
    - **Explainable:** The resulting patterns are directly traceable from the input data.
    """

    # Define a simple TrieNode class inside the function scope
    class TrieNode:
        def __init__(self, step: str):
            self.step = step
            self.children = {}
            self.count = 0
            self.is_end_of_journey = False

    root = TrieNode(step="ROOT")

    # 1. Build the Trie from all user journeys
    for journey_data in request.user_journeys:
        journey = journey_data.get("journey", [])
        node = root
        for step in journey:
            if step not in node.children:
                node.children[step] = TrieNode(step=step)
            node = node.children[step]
            node.count += 1
        node.is_end_of_journey = True

    # 2. Traverse the Trie to find all complete journey patterns
    found_patterns = []

    def find_patterns(node: TrieNode, path: List[str]):
        if node.is_end_of_journey:
            found_patterns.append({"path": path, "frequency": node.count})

        for child_node in node.children.values():
            find_patterns(child_node, path + [child_node.step])

    find_patterns(root, [])

    # 3. Format the patterns for the response
    response_patterns = []
    for i, pattern_data in enumerate(found_patterns):
        path = pattern_data["path"]
        response_patterns.append(
            BehavioralPatternResponse.Pattern(
                pattern_id=f"p_{i}",
                pattern_name=" → ".join(path),
                frequency=pattern_data["frequency"],
                path=path,
            )
        )

    return BehavioralPatternResponse(common_patterns=response_patterns)
