# app/tasks.py
import os
import shutil
from pathlib import Path
from pdf2image import convert_from_path
from sqlalchemy.orm import Session

from app.worker import celery_app
from app.db.session import SessionLocal
from app.crud import crud_presentation
from app.core.config import settings
from app.core.s3 import get_s3_client  # --- CHANGE: Import the new helper ---


@celery_app.task
def process_presentation(session_id: str, s3_key: str):
    """
    Celery task to download a PDF, convert it to images, upload them back,
    and update the database.
    """
    db: Session = SessionLocal()
    # --- CHANGE: Use the centralized S3 client function ---
    s3_client = get_s3_client()

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
                ExtraArgs={"ACL": "public-read", "ContentType": "image/jpeg"},
            )

            # Construct the public URL
            if settings.AWS_S3_ENDPOINT_URL:
                # For MinIO, the URL structure is slightly different
                public_url = f"{settings.AWS_S3_ENDPOINT_URL}/{settings.AWS_S3_BUCKET_NAME}/{public_s3_key}"
            else:
                # For AWS S3
                public_url = f"https://{settings.AWS_S3_BUCKET_NAME}.s3.{settings.AWS_S3_REGION}.amazonaws.com/{public_s3_key}"

            slide_urls.append(public_url)

        # 4. Update the database with the public slide URLs
        if slide_urls:
            # Check if a presentation already exists and update it, or create a new one
            existing_presentation = crud_presentation.presentation.get_by_session(
                db, session_id=session_id
            )
            if existing_presentation:
                crud_presentation.presentation.update(
                    db, db_obj=existing_presentation, obj_in={"slide_urls": slide_urls}
                )
            else:
                crud_presentation.presentation.create_with_session(
                    db, session_id=session_id, slide_urls=slide_urls
                )

    finally:
        # 5. Clean up temporary local files
        shutil.rmtree(temp_dir)
        db.close()

    return {"status": "success", "s3_urls": slide_urls}
