# Image for the quadratic equation solver (Flask app served by Gunicorn)
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py index.html ./

EXPOSE 5000

CMD ["gunicorn", "--workers", "2", "--threads", "4", "--backlog", "2048", "--bind", "0.0.0.0:5000", "app:app"]
