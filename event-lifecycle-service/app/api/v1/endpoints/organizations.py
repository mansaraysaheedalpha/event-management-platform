# app/api/v1/endpoints/organizations.py
"""
Organization-related endpoints including temp image upload.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
import uuid

from app.core.s3 import generate_presigned_post
from app.core.config import settings
from app.api.deps import get_current_user_optional

router = APIRouter(prefix="/organizations", tags=["organizations"])


class TempImageUploadRequest(BaseModel):
    content_type: str
    filename: str


class TempImageUploadResponse(BaseModel):
    url: str
    fields: dict
    s3_key: str
    public_url: str


ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


@router.post(
    "/{org_id}/temp-image-upload",
    response_model=TempImageUploadResponse,
    summary="Generate pre-signed URL for temporary image upload"
)
async def create_temp_image_upload(
    org_id: str,
    request: TempImageUploadRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional)
):
    """
    Generate a pre-signed URL for uploading images directly to S3.

    The uploaded images are stored in a temp/ prefix and can be used
    when creating events or other entities.
    """
    # Validate authentication
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    # Validate content type
    if request.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content type. Allowed types: {', '.join(ALLOWED_CONTENT_TYPES)}"
        )

    # Validate filename
    if not request.filename or len(request.filename) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid filename"
        )

    # Extract file extension
    file_ext = "jpg"
    if "." in request.filename:
        file_ext = request.filename.rsplit(".", 1)[-1].lower()
        if file_ext not in ["jpg", "jpeg", "png", "webp"]:
            file_ext = "jpg"

    # Generate unique S3 key
    unique_id = str(uuid.uuid4())
    s3_key = f"temp/{org_id}/{unique_id}.{file_ext}"

    try:
        # Generate pre-signed POST URL
        presigned = generate_presigned_post(
            object_name=s3_key,
            content_type=request.content_type,
            expires_in=300  # 5 minutes
        )

        # For local MinIO, replace Docker hostname with localhost for browser access
        upload_url = presigned["url"]
        if settings.AWS_S3_ENDPOINT_URL and "minio:" in settings.AWS_S3_ENDPOINT_URL:
            # Replace minio hostname with localhost in the presigned URL
            upload_url = presigned["url"].replace("minio:", "localhost:")
            public_url = f"http://localhost:9000/{settings.AWS_S3_BUCKET_NAME}/{s3_key}"
        else:
            # Production S3
            public_url = f"https://{settings.AWS_S3_BUCKET_NAME}.s3.{settings.AWS_S3_REGION}.amazonaws.com/{s3_key}"

        return TempImageUploadResponse(
            url=upload_url,
            fields=presigned["fields"],
            s3_key=s3_key,
            public_url=public_url
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate upload URL: {str(e)}"
        )
