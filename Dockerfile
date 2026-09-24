FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/app/data/rivertrail.db

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && pip uninstall -y pip

COPY server.py .
COPY public ./public

# Run as a regular user rather than root
RUN useradd --create-home appuser && mkdir -p /app/data && chown -R appuser /app/data
USER appuser

EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=3s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:3000/health')" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:3000", "--workers", "1", "--threads", "4", "server:app"]
