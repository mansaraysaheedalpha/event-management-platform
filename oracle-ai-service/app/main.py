#oracle-ai-service/main.py
from fastapi import FastAPI
from app.features import api

app = FastAPI(title="Oracle Microservice API", version="1.0.0")

app.include_router(api.api_router, prefix="/oracle")


@app.get("/health")
def health_check():
    return {"status": "healthy"}
