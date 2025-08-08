import boto3
from botocore.exceptions import NoCredentialsError
from app.core.config import settings


def get_s3_client():
    """Initializes and returns a boto3 S3 client."""
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION,
    )


def upload_file_to_s3(file_path: str, object_name: str) -> str:
    """Uploads a file to S3 and returns its public URL."""
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION,
    )
    s3_client.upload_file(file_path, settings.AWS_S3_BUCKET_NAME, object_name)
    return f"https://{settings.AWS_S3_BUCKET_NAME}.s3.{settings.AWS_S3_REGION}.amazonaws.com/{object_name}"
