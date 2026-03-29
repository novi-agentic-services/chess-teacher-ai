FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
CMD ["celery", "-A", "app.tasks", "worker", "--loglevel=INFO", "-Q", "twic.download,twic.parse,twic.aggregate"]
