# syntax=docker/dockerfile:1               # optional, but nice to have
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install --with-deps

COPY . .

# Render sets $PORT for you
ENV PORT=8000
CMD ["python", "ghl_sub_account_automation.py",
     "--serve",
     "--host", "0.0.0.0",
     "--port", "8000"]
