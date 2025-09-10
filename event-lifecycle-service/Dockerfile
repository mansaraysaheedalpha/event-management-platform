# event-lifecycle-service/Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed by libraries like pdf2image
RUN apt-get update && apt-get install -y poppler-utils && rm -rf /var/lib/apt/lists/*

# Copy requirements file first to leverage layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# ✅ FIXED: Copy the entire project context, respecting the .dockerignore file
COPY . .

# ✅ ADDED: Explicitly define the command to run the Uvicorn server
# The --host 0.0.0.0 is critical for making the service accessible within Docker's network
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]