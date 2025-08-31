# oracle-ai-service/main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.features import api
from app.models.ai import sentiment
from app.db import models, seed
from app.graphql.router import graphql_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    sentiment.load_model()
    # Seed the database on startup if it's empty
    seed.seed_database()
    yield


app = FastAPI(title="Oracle Microservice API", version="1.0.0", lifespan=lifespan)

app.include_router(api.api_router, prefix="/oracle")
app.include_router(graphql_router, prefix="/graphql")


@app.get("/health")
def health_check():
    return {"status": "healthy"}
