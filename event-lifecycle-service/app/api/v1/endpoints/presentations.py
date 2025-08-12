# app/api/v1/endpoints/presentations.py
import os
import shutil
import uuid
from pathlib import Path
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile
from sqlalchemy.orm import Session
from pdf2image import convert_from_path
from app.tasks import process_presentation

from app.api import deps
from app.db.session import get_db
from app.crud import crud_session, crud_presentation
from app.schemas.token import TokenPayload
from app.schemas.presentation import Presentation

router = APIRouter(tags=["Presentations"])

# IMPORTANT: Define the path to your extracted poppler/bin directory
# You may need to adjust this path depending on where you extracted it.
POPPLER_PATH = r"C:\poppler-24.02.0\Library\bin"


@router.post(
    "/organizations/{orgId}/events/{eventId}/sessions/{sessionId}/presentation",
    response_model=dict,
    status_code=status.HTTP_202_ACCEPTED,
)
def upload_presentation(
    orgId: str,
    eventId: str,
    sessionId: str,
    db: Session = Depends(get_db),
    current_user: TokenPayload = Depends(deps.get_current_user),
    presentation_file: UploadFile = File(...),
):
    """
    Upload a presentation file (PDF), convert it to images, and save the URLs.
    """
    if current_user.org_id != orgId:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized"
        )

    session = crud_session.session.get(db=db, event_id=eventId, session_id=sessionId)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Session not found"
        )

    # --- Real File Processing ---

    # 1. Define paths for saving the files
    # The final images will be in `static/presentations/{sessionId}/`
    output_dir = Path(f"static/presentations/{sessionId}")
    os.makedirs(output_dir, exist_ok=True)

    # Save the uploaded PDF to a temporary location
    temp_pdf_path = output_dir / f"temp_{uuid.uuid4()}.pdf"
    with open(temp_pdf_path, "wb") as buffer:
        shutil.copyfileobj(presentation_file.file, buffer)

    # 2. Convert PDF to a list of images
    # NOTE: This is a blocking operation. For a production app, this
    # should be offloaded to a background worker.
    try:
        images = convert_from_path(temp_pdf_path, poppler_path=POPPLER_PATH)
    except Exception as e:
        # Clean up the temp file if conversion fails
        os.remove(temp_pdf_path)
        raise HTTPException(status_code=500, detail=f"Failed to convert PDF: {e}")

    # 3. Save each image and collect their URLs
    slide_urls = []
    for i, image in enumerate(images):
        slide_filename = f"slide_{i + 1}.jpg"
        slide_path = output_dir / slide_filename
        image.save(slide_path, "JPEG")

        # The URL will be relative to our server root
        slide_urls.append(f"/static/presentations/{sessionId}/{slide_filename}")

    # 4. Clean up the temporary PDF file
    os.remove(temp_pdf_path)

    # --- End Real Processing ---

    # Save the generated slide URLs to the database
    new_presentation = crud_presentation.presentation.create_with_session(
        db, session_id=sessionId, slide_urls=slide_urls
    )

    return new_presentation
