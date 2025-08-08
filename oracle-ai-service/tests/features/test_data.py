from app.features.networking.schemas import MatchmakingRequest

primary_user = MatchmakingRequest.UserProfile(
    user_id="user_A", interests=["python", "fastapi", "docker"]
)

# A list of test cases: (other_user, expected_score, expected_common_interests)
matchmaking_test_cases = [
    # Case 1: Partial match
    (
        MatchmakingRequest.UserProfile(
            user_id="user_B", interests=["python", "fastapi", "react"]
        ),
        0.5,
        ["fastapi", "python"],
    ),
    # Case 2: No match
    (
        MatchmakingRequest.UserProfile(
            user_id="user_C", interests=["finance", "investing"]
        ),
        0.0,
        [],
    ),
    # Case 3: Full match
    (
        MatchmakingRequest.UserProfile(
            user_id="user_D", interests=["python", "fastapi", "docker"]
        ),
        1.0,
        ["docker", "fastapi", "python"],
    ),
]
