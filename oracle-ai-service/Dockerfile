# oracle-ai-service/Dockerfile

FROM pytorch/pytorch:2.3.0-cuda12.1-cudnn8-runtime
WORKDIR /app

# ✅ ADDED: This ensures we use the correct python version for pip
ENV PATH="/opt/conda/bin:$PATH"

COPY requirements.txt .
RUN pip --default-timeout=300 install --no-cache-dir -r requirements.txt

# ✅ FIXED: Copy the entire context, respecting .dockerignore
COPY . .

# CMD is provided by docker-compose.yml