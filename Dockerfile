FROM python:3.12-slim-bookworm

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Source
COPY . .

# Runtime dirs
RUN mkdir -p work logs data

# Non-root user
RUN useradd -r -s /bin/false dansticker && chown -R dansticker:dansticker /app
USER dansticker

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
