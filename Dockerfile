# Use a specific Python 3.9 slim image version for reproducibility
FROM python:3.13.2-slim

# Set the working directory
WORKDIR /app

# Create a non-root user and group
RUN groupadd --system appgroup && \
    useradd --system --gid appgroup --create-home appuser

# Install system dependencies if any (e.g., build tools) - add as needed
# RUN apt-get update && apt-get install -y --no-install-recommends some-package && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .

# Install Python dependencies
# Use --no-cache-dir to reduce image size
# Consider using a virtual environment within the container if preferred
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Change ownership of the app directory to the non-root user
RUN chown -R appuser:appgroup /app

# Switch to the non-root user
USER appuser

# Expose the port the app runs on (matching Gunicorn)
EXPOSE 8080

# Environment variable for Gunicorn workers (default: 2)
# Can be overridden at runtime (e.g., docker run -e GUNICORN_WORKERS=4 ...)
ENV GUNICORN_WORKERS ${GUNICORN_WORKERS:-2}

# Default command to run the application using Gunicorn
# Uses the environment variable for worker count
# Use 'app:app' - module_name:Flask_instance_name
CMD ["sh", "-c", "gunicorn -w ${GUNICORN_WORKERS} -b 0.0.0.0:8080 app:app"]