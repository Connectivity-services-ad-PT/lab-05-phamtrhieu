FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir fastapi uvicorn pydantic requests

# Create non-root user
RUN addgroup --system appgroup \
    && adduser --system --ingroup appgroup --home /app appuser

COPY main.py .

RUN chown -R appuser:appgroup /app
USER appuser

EXPOSE 9000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "9000"]
