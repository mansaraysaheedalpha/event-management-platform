# app/core/s3.py
import boto3
from botocore.exceptions import ClientError
from app.core.config import settings


def get_s3_client():
    """
    Initializes and returns an S3 client.
    Conditionally configures the endpoint_url for local development with MinIO.
    """
    # If the endpoint URL is set in the environment (for MinIO), use it.
    if settings.AWS_S3_ENDPOINT_URL:
        return boto3.client(
            "s3",
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION,
        )
    # Otherwise, it will default to the standard AWS endpoint for production.
    else:
        return boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_S3_REGION,
        )


def generate_presigned_post(
    object_name: str, content_type: str, expires_in: int = 3600
):
    """
    Generates a pre-signed URL and fields for an S3 POST request.
    """
    # --- CHANGE: Use the new centralized S3 client function ---
    s3_client = get_s3_client()
    try:
        response = s3_client.generate_presigned_post(
            Bucket=settings.AWS_S3_BUCKET_NAME,
            Key=object_name,
            Fields={"Content-Type": content_type},
            Conditions=[{"Content-Type": content_type}],
            ExpiresIn=expires_in,
        )
    except ClientError as e:
        print(f"Failed to generate pre-signed URL: {e}")
        return None

    return response
