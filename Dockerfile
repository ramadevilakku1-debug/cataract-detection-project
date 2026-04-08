# Base image
FROM python:3.9-slim

# Set the working directory
WORKDIR /app

# Copy application files
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port your app runs on
EXPOSE 7860

# Command to run the application
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:7860", "app2:app"]