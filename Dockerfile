# Dockerfile
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy   # ⇦ includes chromium + deps

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt       \
    && playwright install --with-deps

COPY . .

# Render will inject $PORT; FastAPI must bind to it
ENV PORT=8000
CMD ["python", "ghl_sub_account_automation.py",
     "--serve",
     "--host", "0.0.0.0",
     "--port", "8000"]

