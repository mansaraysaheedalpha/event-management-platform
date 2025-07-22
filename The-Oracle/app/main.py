from fastapi import FastAPI
from app.api import prediction

# Create the FastAPI app instance
app = FastAPI(
    title="The Oracle AI Service",
    description="AI-powered predictions, analytics, and intelligent recommendations for the event industry.",
    version="1.0.0",
)

# Include the prediction router
app.include_router(prediction.router, prefix="/predict", tags=["Predictions"])


@app.get("/", tags=["Root"])
def read_root():
    """A simple health check endpoint."""
    return {"status": "ok", "message": "Welcome to The Oracle!"}
