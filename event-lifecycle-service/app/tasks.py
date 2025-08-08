import os
import shutil
from pathlib import Path
from pdf2image import convert_from_path
from sqlalchemy.orm import Session

from app.worker import celery_app
from app.db.session import SessionLocal
from app.crud import crud_presentation
from app.core.s3 import upload_file_to_s3

@celery_app.task
def process_presentation(session_id: str, temp_pdf_path: str):
    """
    Celery task to convert PDF to images, upload to S3, and update the database.
    """
    db: Session = SessionLocal()
    temp_image_dir = Path(f"temp_images/{session_id}")
    os.makedirs(temp_image_dir, exist_ok=True)

    try:
        images = convert_from_path(temp_pdf_path)

        slide_urls = []
        for i, image in enumerate(images):
            temp_image_path = temp_image_dir / f"slide_{i + 1}.jpg"
            image.save(temp_image_path, "JPEG")

            s3_object_name = f"presentations/{session_id}/slide_{i + 1}.jpg"

            public_url = upload_file_to_s3(str(temp_image_path), s3_object_name)
            if public_url:
                slide_urls.append(public_url)

        if slide_urls:
            crud_presentation.presentation.create_with_session(
                db, session_id=session_id, slide_urls=slide_urls
            )
    finally:
        os.remove(temp_pdf_path)
        shutil.rmtree(temp_image_dir)
        db.close()

    return {"status": "success", "s3_urls": slide_urls}
