# app/features/management/service.py
import uuid
import random
import time
import jwt
import httpx
from datetime import datetime, timezone
from typing import List, Dict, Any
from fastapi import HTTPException
from sqlalchemy.orm import Session
from app.db import crud
from .schemas import *
from app.core.config import settings


# --- ADAPTER FOR GITHUB APP AUTHENTICATION ---
class DeploymentClient:
    def __init__(
        self, app_id: str, private_key: str, installation_id: str, workflow_url: str
    ):
        self.app_id = app_id
        self.private_key = private_key.replace(
            "\\n", "\n"
        )  # Handles multi-line key from .env
        self.installation_id = installation_id
        self.workflow_url = workflow_url

    def _get_installation_access_token(self) -> str:
        """Generates a short-lived access token for the app installation."""
        # 1. Create a JWT for the App itself
        payload = {
            "iat": int(time.time()) - 60,
            "exp": int(time.time()) + (10 * 60),  # 10 minute expiry
            "iss": self.app_id,
        }
        app_jwt = jwt.encode(payload, self.private_key, algorithm="RS256")

        # 2. Use the App JWT to request an Installation Access Token
        token_url = f"https://api.github.com/app/installations/{self.installation_id}/access_tokens"
        headers = {
            "Authorization": f"Bearer {app_jwt}",
            "Accept": "application/vnd.github.v3+json",
        }

        with httpx.Client() as client:
            response = client.post(token_url, headers=headers)
            response.raise_for_status()
            return response.json()["token"]

    def trigger(self, model_id: str, version: str):
        """Triggers a GitHub Actions workflow_dispatch event using a short-lived token."""
        print(
            f"DELEGATING: Triggering deployment pipeline for {model_id} v{version}..."
        )
        try:
            token = self._get_installation_access_token()
            headers = {
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
            }

            with httpx.Client() as client:
                response = client.post(
                    self.workflow_url,
                    headers=headers,
                    json={
                        "ref": "main",
                        "inputs": {"model_id": model_id, "version": version},
                    },
                )
                response.raise_for_status()
            print("Pipeline triggered successfully.")
            return True
        except Exception as e:
            print(f"ERROR: Failed to trigger deployment pipeline: {e}")
            raise HTTPException(
                status_code=502, detail="Failed to trigger deployment pipeline."
            )


ettings = get_settings()
# Instantiate the client for the service to use
deployment_client = DeploymentClient(
    app_id=settings.GITHUB_APP_ID,
    private_key=settings.GITHUB_PRIVATE_KEY,
    installation_id=settings.GITHUB_INSTALLATION_ID,
    workflow_url=settings.GITHUB_WORKFLOW_DISPATCH_URL,
)


# --- SERVICE FUNCTIONS ---
def deploy_model(db: Session, request: ModelDeployRequest) -> ModelDeployResponse:
    """Validates a model version against the registry and triggers a deployment."""
    model_data = crud.get_kb_entry(db, category="model_registry", key=request.model_id)
    if not model_data or model_data.get("version") != request.version:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{request.model_id}' version '{request.version}' not found.",
        )

    # Delegate to the deployment client
    deployment_client.trigger(model_id=request.model_id, version=request.version)

    return ModelDeployResponse(
        deployment_id=f"deploy_{uuid.uuid4().hex[:12]}",
        status="in_progress",
        deployment_time=datetime.now(timezone.utc),
    )


monitoring_client = MonitoringClient(
    api_key=settings.DATADOG_API_KEY, app_key=settings.DATADOG_APP_KEY
)
def get_model_versions(db: Session) -> ModelVersionsResponse:
    """Retrieves a list of available ML model versions from the DB."""
    # This now queries the database via our CRUD function
    raw_models_data = crud.get_kb_category(db, category="model_registry")
    # The data from crud is in the format [{"key": {"data"}}]
    models_data = [list(item.values())[0] for item in raw_models_data]

    model_versions = [
        ModelVersionsResponse.ModelVersion(**data) for data in models_data
    ]
    return ModelVersionsResponse(models=model_versions)


def get_model_performance(db: Session, model_id: str) -> ModelPerformanceResponse:
    """Validates a model ID and retrieves its performance metrics."""
    model_data = crud.get_kb_entry(db, category="model_registry", key=model_id)
    if not model_data:
        raise HTTPException(
            status_code=404, detail=f"Model '{model_id}' not found in registry."
        )

    
    # Fetch data from the monitoring client
    metrics = monitoring_client.get_metrics(model_id)

    return ModelPerformanceResponse(model_id=model_id, **metrics)
