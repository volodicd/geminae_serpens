FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    sudo \
    && rm -rf /var/lib/apt/lists/*

# Create app directory
WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app/

# Create volume mount points
VOLUME ["/app/configs", "/etc/cloudflared", "/var/www/port-config"]
ARG DOCKER_GID=987
# Run as non-root user
RUN groupadd -g ${DOCKER_GID} docker &&\
    useradd -m -s /bin/bash serpens && \
    usermod -aG docker serpens && \
    usermod -aG sudo serpens && \
    echo 'serpens ALL=(ALL) NOPASSWD: /bin/systemctl restart cloudflared' >> /etc/sudoers

USER serpens

# Expose API port
EXPOSE 8000

# Run the API
CMD ["python", "-m", "uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
