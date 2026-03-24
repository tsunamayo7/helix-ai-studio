# Helix AI Studio — Docker image
FROM python:3.12-slim

WORKDIR /app

# Install uv
RUN pip install uv

# Copy project files
COPY pyproject.toml uv.lock ./
RUN uv sync --no-dev

COPY helix_studio/ helix_studio/
COPY run.py .

# Create data directory
RUN mkdir -p data

EXPOSE 8502

CMD ["uv", "run", "python", "run.py"]
