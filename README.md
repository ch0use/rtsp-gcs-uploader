# rtsp-gcs-uploader
Periodically grabs a single frame from an RTSP camera stream and uploads it to a Google Cloud Storage (GCS) bucket. It is meant to run as a long-lived container (e.g. on a Synology NAS) and keep a "latest snapshot" image fresh.
