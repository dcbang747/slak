FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

# Bind to $PORT when the host injects one (e.g. Render); fall back to 8000 for
# local docker-compose. Shell form so ${PORT:-8000} is expanded.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
