FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    fastapi==0.115.12 \
    uvicorn==0.34.2

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
