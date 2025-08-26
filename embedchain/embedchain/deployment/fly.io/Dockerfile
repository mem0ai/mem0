FROM python:3.11-slim

# Create a non-root user and group
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# Set the working directory
WORKDIR /app

# Copy application files and adjust permissions in a single step
COPY . /app
RUN chown -R appuser:appgroup /app

# Install dependencies before switching to non-root user
RUN pip install --no-cache-dir -r requirements.txt

# Switch to non-root user
USER appuser

# Expose application port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
