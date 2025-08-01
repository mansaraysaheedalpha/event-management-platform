from fastapi import FastAPI
from app.api.v1.api import api_router

app = FastAPI(title="Oracle Microservice API", version="1.0.0")

app.include_router(api_router, prefix="/oracle/v1")


@app.get("/health")
def health_check():
    return {"status": "healthy"}
