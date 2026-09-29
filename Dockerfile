FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    gettext \
    libpq5 \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# PIP_TRUSTED_HOST=1 for local Windows Docker Desktop TLS issues; CI/prod leave unset.
ARG PIP_TRUSTED_HOST=0
RUN if [ "$PIP_TRUSTED_HOST" = "1" ]; then \
      pip install --no-cache-dir \
        --trusted-host pypi.org \
        --trusted-host files.pythonhosted.org \
        -r requirements.txt; \
    else \
      pip install --no-cache-dir -r requirements.txt; \
    fi

COPY . .

RUN chmod +x /app/entrypoint.sh \
    && SECRET_KEY=build-only-collectstatic-key \
       DB_USER=build \
       DB_PASSWORD=build \
       DB_NAME=build \
       DB_HOST=localhost \
       DEBUG=False \
       ALLOWED_HOSTS=localhost \
       python manage.py collectstatic --noinput

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
