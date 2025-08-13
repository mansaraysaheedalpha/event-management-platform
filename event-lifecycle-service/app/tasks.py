# app/tasks.py

import os
import shutil
from pathlib import Path
from pdf2image import convert_from_path
from sqlalchemy.orm import Session
import boto3

from app.worker import celery_app
from app.db.session import SessionLocal
from app.crud import crud_presentation
from app.core.config import settings


@celery_app.task
def process_presentation(session_id: str, s3_key: str):
    """
    Celery task to download a PDF from S3, convert it to images,
    upload them back to S3, and update the database.
    """
    db: Session = SessionLocal()
    s3_client = boto3.client("s3", region_name=settings.AWS_S3_REGION)

    temp_dir = Path(f"/tmp/{session_id}")
    os.makedirs(temp_dir, exist_ok=True)
    temp_pdf_path = temp_dir / "original.pdf"

    try:
        # 1. Download the original PDF from the staging area in S3
        s3_client.download_file(settings.AWS_S3_BUCKET_NAME, s3_key, str(temp_pdf_path))

        # 2. Convert PDF to images
        images = convert_from_path(str(temp_pdf_path))

        slide_urls = []
        for i, image in enumerate(images):
            temp_image_path = temp_dir / f"slide_{i + 1}.jpg"
            image.save(temp_image_path, "JPEG")

            # 3. Upload each image slide to a permanent location in S3
            public_s3_key = f"presentations/{session_id}/slide_{i + 1}.jpg"
            s3_client.upload_file(
                str(temp_image_path),
                settings.AWS_S3_BUCKET_NAME,
                public_s3_key,
                ExtraArgs={"ACL": "public-read"},  # Make slides publicly viewable
            )

            # Construct the public URL
            public_url = f"https://{settings.AWS_S3_BUCKET_NAME}.s3.{settings.AWS_S3_REGION}.amazonaws.com/{public_s3_key}"
            slide_urls.append(public_url)

        # 4. Update the database with the public slide URLs
        if slide_urls:
            crud_presentation.presentation.create_with_session(
                db, session_id=session_id, slide_urls=slide_urls
            )

    finally:
        # 5. Clean up temporary local files
        shutil.rmtree(temp_dir)
        db.close()

    return {"status": "success", "s3_urls": slide_urls}
