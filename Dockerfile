FROM python:3.12-slim

WORKDIR /server

# Install dependencies first (layer-cached until requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY server/ ./server/
COPY server.py .
COPY server_configs/ ./server_configs/
COPY completion_resources/ ./completion_resources/
COPY models_service_data/ ./models_service_data/

# session_storage is intentionally excluded from the image;
# it is expected to be supplied via a bind-mount or named volume at runtime.
VOLUME ["/server/session_storage"]

EXPOSE 8000

CMD ["python", "server.py", "server_configs/docker_context.json"]
