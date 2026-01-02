# Use lightweight Python image
FROM python:3.10-slim

# Set environment variables to prevent Python from buffering stdout/stderr
ENV PYTHONUNBUFFERED=1

# Install FFmpeg and system fonts dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg libfontconfig1 && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application (gifs, fonts, script)
COPY . .

# Run the script
CMD ["python", "main.py"]
