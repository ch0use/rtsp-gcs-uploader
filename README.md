# rtsp-uploader

Periodically grabs a single frame from an RTSP camera stream and uploads it to a Google Cloud Storage (GCS) bucket. It is meant to run as a long-lived container (e.g. on a Synology NAS) and keep a "latest snapshot" image fresh.

## How it works

[`loop.py`](loop.py) runs forever:

1. Authenticates to GCP with a service account key mounted at `/auth/sa-key.json`.
2. Deletes any previous frame at `/tmp/<CAM_FILE_NAME>` so a failed capture can never re-upload a stale image.
3. Runs `ffmpeg` to capture one frame from `rtsp://<CAM_CREDS>@<CAM_IP>` over TCP (`-frames:v 1 -update 1`).
4. On success, uploads the frame to `gs://<GCS_BUCKET>/<CAM_FILE_NAME>` with `Cache-Control: public, max-age=60`.
5. Logs the result (errors in capture or upload are logged, not fatal) and sleeps `SLEEP_INTERVAL` seconds.
6. Repeats. `Ctrl+C` (SIGINT) exits cleanly.

All output is unbuffered, so logs appear immediately in `docker logs` or Container Manager.

## Requirements

### Runtime (provided by the Docker image)

- Python 3.12
- `ffmpeg` (installed from Debian repos; a recent version is needed for the `-update 1` flag)
- Python package `google-cloud-storage`

### Environment variables (all required)

| Variable         | Description                                                 | Example                  |
| ---------------- | ----------------------------------------------------------- | ------------------------ |
| `CAM_IP`         | Camera IP address (and port/path if needed)                 | `192.168.1.50`           |
| `CAM_CREDS`      | Camera credentials as `user:password`                       | `admin:secret`           |
| `CAM_FILE_NAME`  | Output object name in the bucket (also the temp file name)  | `skyview.jpg`            |
| `GCS_BUCKET`     | Destination bucket name (no `gs://` prefix)                 | `my-bucket`              |
| `SLEEP_INTERVAL` | Seconds between captures (float allowed)                    | `60`                     |

The script exits at startup with a `KeyError` if any are missing.

### GCP credentials

- A service account JSON key mounted into the container at `/auth/sa-key.json`.
- The service account needs permission to create/overwrite objects in the bucket (e.g. **Storage Object Admin**, or a custom role with `storage.objects.create` and `storage.objects.delete`/`update` limited to that bucket).

### Network

The container must be able to reach the camera's RTSP port (554 by default). If the default bridge network can't route to the camera, use host networking.

## Building the Docker image

The [`Dockerfile`](Dockerfile) is based on `python:3.12-slim`, installs `ffmpeg` and `google-cloud-storage`, copies `loop.py`, and runs it.

The image must be built for the CPU architecture of the machine that runs it. The Synology DS725+ is x86_64, so build for `linux/amd64`. On an Apple Silicon Mac a plain `docker build` produces an `arm64` image, which fails on the NAS with `exec /usr/local/bin/python: exec format error`.

Use `buildx` with an explicit platform (this requires the `docker-buildx` plugin, e.g. `brew install docker-buildx`, and a running Docker daemon):

```bash
docker buildx build --platform linux/amd64 -t rtsp-gcs-uploader-py:latest --load .
```

Verify the architecture before exporting (it should print `linux/amd64`):

```bash
docker image inspect rtsp-gcs-uploader-py:latest --format '{{.Os}}/{{.Architecture}}'
```

On an x86_64 machine building for an x86_64 target, a plain `docker build -t rtsp-gcs-uploader-py:latest .` is sufficient. To check the NAS architecture, run `uname -m` over SSH (expect `x86_64`).

### Exporting for a NAS

```bash
docker save rtsp-gcs-uploader-py:latest > rtsp-gcs-uploader-py.tar
```

Copy the tarball to the NAS, then in Synology Container Manager: **Image → Action → Import → Add From File**.

## Running the container

```bash
docker run -d --name rtsp-gcs-uploader-py --restart unless-stopped \
  -e CAM_IP=192.168.1.50 \
  -e CAM_CREDS=admin:secret \
  -e CAM_FILE_NAME=skyview.jpg \
  -e GCS_BUCKET=my-bucket \
  -e SLEEP_INTERVAL=60 \
  -v /path/to/sa-key.json:/auth/sa-key.json:ro \
  rtsp-gcs-uploader-py:latest
```

Check progress with:

```bash
docker logs -f rtsp-gcs-uploader-py
```

On Synology Container Manager, set the same environment variables, mount the key file read-only at `/auth/sa-key.json`, and enable auto-restart.

## Updating

After changing `loop.py` (or rebuilding for a different architecture), rebuild and re-export the image, then on the Synology:

1. Stop and delete the existing container.
2. In **Image**, delete the old `rtsp-gcs-uploader-py:latest` (otherwise the old image may be reused).
3. Import the new tarball.
4. Recreate the container with the same environment variables, volume mount and network settings.
