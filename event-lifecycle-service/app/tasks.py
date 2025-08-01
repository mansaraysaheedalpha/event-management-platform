import os
import shutil
from pathlib import Path
from pdf2image import convert_from_path
from sqlalchemy.orm import Session
from app.core.s3 import upload_file_to_s3

from app.worker import celery_app
from app.db.session import SessionLocal
from app.crud import crud_presentation

# Define the path to your Poppler bin directory within the Docker container
# It's usually in the system PATH, but being explicit is safer.
POPPLER_PATH = None  # Often not needed in Docker if installed via apt-get


@celery_app.task
def process_presentation(session_id: str, temp_pdf_path: str):
    """
    Celery task to convert a PDF to images, save them, and update the database.
    """
    db: Session = SessionLocal()
    temp_image_dir = Path(f"temp_images/{session_id}")
    os.makedirs(temp_image_dir, exist_ok=True)
    try:
        images = convert_from_path(
            temp_pdf_path
        )  # poppler_path is not needed in our Docker container

        slide_urls = []
        for i, image in enumerate(images):
            # Save image temporarily to disk
            temp_image_path = temp_image_dir / f"slide_{i + 1}.jpg"
            image.save(temp_image_path, "JPEG")

            # Define the final path in the S3 bucket
            s3_object_name = f"presentations/{session_id}/slide_{i + 1}.jpg"

            # Upload the image to S3 and get its public URL
            public_url = upload_file_to_s3(str(temp_image_path), s3_object_name)
            if public_url:
                slide_urls.append(public_url)

        if slide_urls:
            crud_presentation.presentation.create_with_session(
                db, session_id=session_id, slide_urls=slide_urls
            )
    finally:
        # Clean up all temporary files and the DB session
        os.remove(temp_pdf_path)
        shutil.rmtree(temp_image_dir)
        db.close()

    return {"status": "success", "s3_urls": slide_urls}
