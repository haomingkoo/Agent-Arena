FROM python:3.14-slim

WORKDIR /app

# Install Node.js for frontend build
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY . .

# Build frontend
RUN cd frontend && npm install && npm run build

EXPOSE 8000

CMD uvicorn api.app:app --host 0.0.0.0 --port ${PORT:-8000}
