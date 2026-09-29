#!/bin/sh
set -e
python manage.py migrate --noinput
python manage.py compilemessages
exec gunicorn \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${GUNICORN_WORKERS:-3}" \
  --forwarded-allow-ips='*' \
  granitanalytics.wsgi:application
