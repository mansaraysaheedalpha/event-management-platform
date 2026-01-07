# event-lifecycle-service/Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed by libraries like pdf2image and curl for healthcheck
RUN apt-get update && apt-get install -y poppler-utils curl && rm -rf /var/lib/apt/lists/*

# Create a non-root user for security
RUN groupadd --system --gid 1001 appgroup && \
    useradd --system --uid 1001 --gid appgroup appuser

# Copy requirements file first to leverage layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project context, respecting the .dockerignore file
COPY . .

# Set ownership of the app directory to the non-root user
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8000

# Run the Uvicorn server
# The --host 0.0.0.0 is critical for making the service accessible within Docker's network
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
