FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Production WSGI server. Platforms that inject $PORT (Render, Railway, Fly,
# Cloud Run, Heroku) are honoured via the shell-form CMD below.
CMD gunicorn app:app --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 60
