import strawberry
from strawberry.types import Info
from .types import SentimentType
from ..models.ai.sentiment import sentiment_model

@strawberry.type
class Query:
    @strawberry.field
    def sentiment(self, text: str) -> SentimentType:
        result = sentiment_model.predict(text)
        return SentimentType(label=result['label'], score=result['score'])
