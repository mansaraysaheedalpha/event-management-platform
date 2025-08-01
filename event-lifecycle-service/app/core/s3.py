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


def upload_file_to_s3(file_path: str, object_name: str) -> str | None:
    """
    Uploads a file to an S3 bucket and returns its public URL.
    :param file_path: Path to the file to upload.
    :param object_name: S3 object name (path/filename in the bucket).
    :return: The public URL of the uploaded file, or None if upload fails.
    """
    s3_client = get_s3_client()
    try:
        s3_client.upload_file(file_path, settings.AWS_S3_BUCKET_NAME, object_name)
        # Construct the public URL
        url = f"https://{settings.AWS_S3_BUCKET_NAME}.s3.{settings.AWS_S3_REGION}.amazonaws.com/{object_name}"
        return url
    except (NoCredentialsError, FileNotFoundError):
        return None
