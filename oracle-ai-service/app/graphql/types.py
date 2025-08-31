import strawberry
import typing

@strawberry.type
class SentimentType:
    label: str
    score: float
