FROM python:3.9-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Default command for the API service; can be overridden.
CMD ["gunicorn", "-b", "0.0.0.0:8080", "app:app"]
