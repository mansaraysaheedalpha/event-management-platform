#app/Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install poppler-utils for pdf2image
RUN apt-get update && apt-get install -y poppler-utils

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./app /app