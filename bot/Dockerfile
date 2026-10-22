FROM python:3.12-slim AS build

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install -r requirements.txt

FROM python:3.12-slim AS runtime

RUN groupadd --system app \
    && useradd --system --gid app app \
    && mkdir -p /app \
    && chown app:app /app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

COPY --from=build /opt/venv /opt/venv
COPY --chown=app:app app ./app
COPY --chown=app:app pyproject.toml ./

USER app

EXPOSE 8080

CMD ["python", "-m", "app.main"]
