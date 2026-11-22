FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

# Shown in the page footer and returned by /api/emi.
# docker build -t emi-web:1.1 --build-arg APP_VERSION=1.1 app/
ARG APP_VERSION=1.0
ENV APP_VERSION=${APP_VERSION}

# run as a non-root user (numeric UID, so Kubernetes can check runAsNonRoot)
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin appuser
USER 10001

EXPOSE 5000
# --keep-alive 75: longer than the NGINX ingress upstream keep-alive (60 s), so NGINX never
# reuses a connection that gunicorn has just closed (that race gives random 502s on POSTs).
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--keep-alive", "75", "app:app"]
