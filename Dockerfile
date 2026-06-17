FROM python:3.12-slim

LABEL maintainer="ToAD Contributors"
LABEL description="ToAD - Centralized Active Directory Audit Platform"

# Install system dependencies
RUN apt update && apt install -y --no-install-recommends \
    docker.io \
    git \
    tzdata \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Clone and install AD-Miner
RUN git clone --depth 1 https://github.com/Mazars-Tech/AD_Miner.git /opt/AD_Miner \
    && pip install --no-cache-dir -r /opt/AD_Miner/requirements.txt

# Install ToAD dependencies
RUN pip install --no-cache-dir \
    fastapi==0.115.0 \
    uvicorn[standard]==0.32.0 \
    python-multipart==0.0.12 \
    requests==2.32.3 \
    pyyaml==6.0.2

# Copy application files
COPY web/app.py /app/app.py
COPY web/index.html /src/index.html
COPY web/setup.html /src/setup.html

# Create necessary directories
RUN mkdir -p /data/config /src

WORKDIR /app

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:80/ || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "80"]
