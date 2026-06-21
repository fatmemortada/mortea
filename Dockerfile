FROM python:3.14-slim
 
# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV GUNICORN_MASTER=true
ENV GUNICORN_WORKER=false
 
# Install system dependencies for weasyprint
RUN apt-get update && apt-get install -y \
    libgobject-2.0-0 \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libpangocairo-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*
 
# Set work directory
WORKDIR /app
 
# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
 
# Copy project
COPY . .
 
# Collect static files
RUN python manage.py collectstatic --no-input
 
# Run gunicorn — 2 workers with 2 threads each for SQLite concurrency, preload for scheduler
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8080", "--workers", "2", "--threads", "2", "--timeout", "120", "--preload"]