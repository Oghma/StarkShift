FROM python:3.12-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libgmp3-dev \
    && rm -rf /var/lib/apt/lists/*

# Install poetry
RUN pip install --no-cache-dir poetry

# Copy only necessary files
COPY pyproject.toml poetry.lock ./
COPY starkshift ./starkshift
COPY config ./config/

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --no-dev --no-interaction --no-ansi

ENTRYPOINT ["poetry", "run", "python", "-m", "starkshift"]
CMD ["config/config.yml"]
