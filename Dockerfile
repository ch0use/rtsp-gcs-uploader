FROM python:3.12-slim

# Install ffmpeg (Debian repos will pull a version >= 5.x)
RUN apt-get update && \
    apt-get install -y --no-install-recommends ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Install the GCS client library
RUN pip install --no-cache-dir google-cloud-storage

# Copy the script
COPY loop.py /loop.py

# Run the script (unbuffered so logs show up immediately)
CMD ["python", "-u", "/loop.py"]