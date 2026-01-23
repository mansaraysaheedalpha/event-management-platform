# app/core/s3.py
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from app.core.config import settings

# Maximum file size for presentation uploads (100MB)
MAX_UPLOAD_SIZE_BYTES = 100 * 1024 * 1024


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
            config=Config(signature_version="s3v4"),
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
    object_name: str,
    content_type: str,
    expires_in: int = 3600,
    max_size_bytes: int = MAX_UPLOAD_SIZE_BYTES,
    public_read: bool = False,
):
    """
    Generates a pre-signed URL and fields for an S3 POST request.
    Includes file size limit for security.

    Args:
        object_name: The S3 object key (path) for the uploaded file
        content_type: The MIME type of the file
        expires_in: URL expiration time in seconds
        max_size_bytes: Maximum allowed file size
        public_read: If True, sets ACL to public-read for public access
    """
    s3_client = get_s3_client()

    fields = {"Content-Type": content_type}
    conditions = [
        {"Content-Type": content_type},
        ["content-length-range", 1, max_size_bytes],
    ]

    # Add public-read ACL if requested
    if public_read:
        fields["acl"] = "public-read"
        conditions.append({"acl": "public-read"})

    # Let ClientError exceptions propagate up to the caller for debugging
    response = s3_client.generate_presigned_post(
        Bucket=settings.AWS_S3_BUCKET_NAME,
        Key=object_name,
        Fields=fields,
        Conditions=conditions,
        ExpiresIn=expires_in,
    )
    return response


def sanitize_filename_for_header(filename: str) -> str:
    """
    Sanitize filename for use in Content-Disposition header to prevent header injection.
    Removes or escapes characters that could be used for injection attacks.
    """
    # Remove any newlines or carriage returns (header injection prevention)
    filename = filename.replace("\r", "").replace("\n", "")
    # Escape double quotes
    filename = filename.replace('"', '\\"')
    # Remove any control characters
    filename = "".join(c for c in filename if ord(c) >= 32)
    # Limit length to prevent buffer issues
    if len(filename) > 200:
        name, ext = filename.rsplit(".", 1) if "." in filename else (filename, "")
        filename = name[:195] + ("." + ext if ext else "")
    return filename


def extract_s3_key_from_url(url: str) -> str | None:
    """
    Extract the S3 object key from a full S3 URL.

    Handles URLs in formats:
    - https://bucket-name.s3.region.amazonaws.com/path/to/file
    - https://bucket-name.s3.amazonaws.com/path/to/file
    - http://localhost:9000/bucket-name/path/to/file (MinIO)

    Returns the object key (path/to/file) or None if not a valid S3 URL.
    """
    import re
    from urllib.parse import urlparse, unquote

    parsed = urlparse(url)

    # Standard S3 URL: bucket-name.s3.region.amazonaws.com/key
    # or bucket-name.s3.amazonaws.com/key
    s3_pattern = rf"^{re.escape(settings.AWS_S3_BUCKET_NAME)}\.s3(?:\.[^.]+)?\.amazonaws\.com$"
    if re.match(s3_pattern, parsed.netloc):
        # Key is the path without leading slash
        return unquote(parsed.path.lstrip("/"))

    # MinIO URL: localhost:9000/bucket-name/key
    if "localhost" in parsed.netloc or "minio" in parsed.netloc:
        path_parts = parsed.path.lstrip("/").split("/", 1)
        if len(path_parts) == 2 and path_parts[0] == settings.AWS_S3_BUCKET_NAME:
            return unquote(path_parts[1])

    return None


def generate_presigned_download_url(
    object_key: str,
    filename: str,
    expires_in: int = 300,  # 5 minutes default
) -> str:
    """
    Generates a pre-signed GET URL for secure file download.
    The URL includes Content-Disposition header to trigger download with the original filename.

    Args:
        object_key: The S3 object key (path) to the file
        filename: The filename to use for the downloaded file
        expires_in: URL expiration time in seconds (default 5 minutes)

    Returns:
        A pre-signed URL string for downloading the file
    """
    # Sanitize filename to prevent header injection
    safe_filename = sanitize_filename_for_header(filename)

    s3_client = get_s3_client()
    url = s3_client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": settings.AWS_S3_BUCKET_NAME,
            "Key": object_key,
            "ResponseContentDisposition": f'attachment; filename="{safe_filename}"',
        },
        ExpiresIn=expires_in,
    )

    # For local dev with MinIO, replace internal hostname with localhost
    if settings.AWS_S3_ENDPOINT_URL and "minio:9000" in url:
        url = url.replace("minio:9000", "localhost:9000")

    return url
