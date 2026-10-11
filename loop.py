#!/usr/bin/env python3
import os
import subprocess
import sys
import time

from google.cloud import storage

CAM_FILE_NAME = os.environ["CAM_FILE_NAME"]
CAM_CREDS = os.environ["CAM_CREDS"]
CAM_IP = os.environ["CAM_IP"]
GCS_BUCKET = os.environ["GCS_BUCKET"]
SLEEP_INTERVAL = float(os.environ["SLEEP_INTERVAL"])

LOCAL_PATH = f"/tmp/{CAM_FILE_NAME}"
GCS_URI = f"gs://{GCS_BUCKET}/{CAM_FILE_NAME}"


def capture_frame():
    return subprocess.run([
        "ffmpeg", "-y", "-loglevel", "warning",
        "-rtsp_transport", "tcp",
        "-i", f"rtsp://{CAM_CREDS}@{CAM_IP}",
        "-frames:v", "1", "-update", "1",
        LOCAL_PATH,
    ]).returncode == 0


def main():
    # Authenticate with GCP using a mounted Service Account key
    client = storage.Client.from_service_account_json("/auth/sa-key.json")
    bucket = client.bucket(GCS_BUCKET)

    while True:
        print("Capturing frame from RTSP stream...", flush=True)

        # Remove old frame to prevent stale uploads on failure
        try:
            os.remove(LOCAL_PATH)
        except FileNotFoundError:
            pass

        if capture_frame():
            print(f"Uploading frame to {GCS_URI}...", flush=True)
            try:
                blob = bucket.blob(CAM_FILE_NAME)
                # Set the Cache-Control header as part of the upload
                blob.cache_control = "public, max-age=60"
                blob.upload_from_filename(LOCAL_PATH)
                print("Upload complete.", flush=True)
            except Exception as e:
                print(f"Error: Failed to upload frame: {e}", flush=True)
        else:
            print("Error: Failed to capture frame.", flush=True)

        print(f"Sleeping for {SLEEP_INTERVAL:g} seconds...", flush=True)
        time.sleep(SLEEP_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)

