# =============================================================================
# Dockerfile — The Mintlify Sentinel
#
# BUILD:
#   docker build -t mintlify-sentinel .
#
# RUN (default — uses bundled input fixtures):
#   docker run --rm mintlify-sentinel
#
# RUN (with mounted volumes for custom specs and output retrieval):
#   docker run --rm \
#     -v "$(pwd)/input:/app/input" \
#     -v "$(pwd)/output:/app/output" \
#     mintlify-sentinel
#
# RUN (with explicit CLI flags):
#   docker run --rm \
#     -v "$(pwd)/input:/app/input" \
#     -v "$(pwd)/output:/app/output" \
#     mintlify-sentinel \
#     python main.py --baseline input/v1.json --target input/v2.json
# =============================================================================

FROM python:3.12-slim

# WeasyPrint (used by architect_pdf.py) requires Cairo and Pango native libs.
# These are installed before pip so the layer is cached independently of
# application code changes.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first — Docker caches this layer until requirements.txt
# changes. Source code edits do not invalidate the pip install layer.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source (respects .dockerignore — no tests, no .git, no output)
COPY . .

# Default command: run the full 4-stage pipeline with bundled input fixtures.
# Override by passing arguments after the image name:
#   docker run --rm mintlify-sentinel python main.py --baseline ...
CMD ["python", "main.py"]
