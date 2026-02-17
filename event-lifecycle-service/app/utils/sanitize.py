# app/utils/sanitize.py
import os


def sanitize_filename(filename: str) -> str:
    """Strip path components and reject dangerous filenames.

    Returns the basename of the provided filename, raising ValueError
    if the result is empty, hidden, or contains path traversal.
    """
    basename = os.path.basename(filename)
    if not basename or basename.startswith(".") or ".." in basename:
        raise ValueError("Invalid filename")
    return basename
