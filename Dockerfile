FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /service

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev curl \
    && rm -rf /var/lib/apt/lists/*

COPY app /service/app
COPY deploy /service/deploy
COPY pyproject.toml README.md /service/

RUN pip install --upgrade pip && pip install .

EXPOSE 8000 9000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
