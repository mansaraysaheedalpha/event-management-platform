# app/core/s3.py
import boto3
from botocore.exceptions import NoCredentialsError, ClientError
from app.core.config import settings


def generate_presigned_post(
    object_name: str, content_type: str, expires_in: int = 3600
):
    """
    Generates a pre-signed URL and fields for an S3 POST request.
    This allows a client to upload a file directly to S3.

    :param object_name: The key (path/filename) for the object in S3.
    :param content_type: The MIME type of the file being uploaded.
    :param expires_in: Time in seconds for the pre-signed post to remain valid.
    :return: A dictionary containing the URL and form fields, or None if error.
    """
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_S3_REGION,
    )
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
