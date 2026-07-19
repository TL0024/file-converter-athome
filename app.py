from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
import time
import uuid
import webbrowser
import zipfile
from pathlib import Path
from threading import Lock, Timer
from typing import Any

from flask import Flask, abort, jsonify, render_template, request, send_file
from flask.typing import ResponseReturnValue
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
from werkzeug.serving import make_server

from converter import ConversionError, ConversionManager, output_filename
from lifecycle import BrowserSessionManager

APP_DIRECTORY = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
app = Flask(
    __name__,
    static_folder=str(APP_DIRECTORY / "static"),
    template_folder=str(APP_DIRECTORY / "templates"),
)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2 GiB per batch
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0

converter = ConversionManager()
BROWSER_SESSIONS = BrowserSessionManager()
JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = Lock()
MAX_FILES = 50
JOB_TTL_SECONDS = 2 * 60 * 60


def cleanup_expired_jobs() -> None:
    cutoff = time.time() - JOB_TTL_SECONDS
    expired: list[dict] = []
    with JOBS_LOCK:
        for job_id, job in list(JOBS.items()):
            if job["created"] < cutoff:
                expired.append(JOBS.pop(job_id))
    for job in expired:
        shutil.rmtree(job["directory"], ignore_errors=True)


def cleanup_all_jobs() -> None:
    """Remove all temporary conversion data during a normal process exit."""
    with JOBS_LOCK:
        jobs = list(JOBS.values())
        JOBS.clear()
    for job in jobs:
        shutil.rmtree(job["directory"], ignore_errors=True)


atexit.register(cleanup_all_jobs)


@app.before_request
def maintain_job_store() -> None:
    cleanup_expired_jobs()


@app.get("/")
def index() -> str:
    return render_template(
        "index.html",
        browser_session_token=BROWSER_SESSIONS.register(),
    )


@app.post("/api/browser/<session_token>/heartbeat")
def browser_heartbeat(session_token: str) -> ResponseReturnValue:
    if not BROWSER_SESSIONS.heartbeat(session_token):
        abort(404, description="This browser session is no longer active.")
    return ("", 204)


@app.post("/api/browser/<session_token>/closed")
def browser_closed(session_token: str) -> ResponseReturnValue:
    if not BROWSER_SESSIONS.close(session_token):
        abort(404, description="This browser session is no longer active.")
    return ("", 204)


@app.get("/api/capabilities")
def capabilities() -> ResponseReturnValue:
    return jsonify(converter.capabilities())


@app.post("/api/convert")
def convert_files() -> ResponseReturnValue:
    uploads = request.files.getlist("files")
    targets = request.form.getlist("targets")

    if not uploads:
        return jsonify({"error": "Choose at least one file to convert."}), 400
    if len(uploads) > MAX_FILES:
        return jsonify({"error": f"A batch can contain at most {MAX_FILES} files."}), 400
    if len(targets) != len(uploads):
        return jsonify({"error": "Every file needs an output format."}), 400

    job_id = uuid.uuid4().hex
    job_dir = Path(tempfile.mkdtemp(prefix=f"fileconverterathome-{job_id[:8]}-"))
    results: list[dict[str, Any]] = []
    successful_files: list[dict[str, Any]] = []
    used_names: set[str] = set()

    for upload, target in zip(uploads, targets, strict=True):
        original_name = upload.filename or "untitled"
        result: dict[str, Any] = {"input_name": original_name}
        try:
            source_format = converter.detect_format(original_name)
            target = target.lower().strip().lstrip(".")
            converter.validate_conversion(source_format, target)

            source_path = job_dir / f"source-{uuid.uuid4().hex}.{source_format}"
            upload.save(source_path)
            if not source_path.exists() or source_path.stat().st_size == 0:
                raise ConversionError("The uploaded file is empty.")

            download_name = output_filename(original_name, target, used_names)
            output_path = job_dir / f"output-{uuid.uuid4().hex}.{target}"
            note = converter.convert(source_path, source_format, output_path, target)
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise ConversionError("The converter did not produce a usable file.")

            file_id = uuid.uuid4().hex
            file_record = {
                "id": file_id,
                "path": output_path,
                "download_name": download_name,
            }
            successful_files.append(file_record)
            result.update(
                {
                    "status": "success",
                    "file_id": file_id,
                    "output_name": download_name,
                    "size": output_path.stat().st_size,
                    "note": note,
                }
            )
        except ConversionError as exc:
            result.update({"status": "error", "error": str(exc)})
        except Exception:
            app.logger.exception("Unexpected conversion failure for %s", original_name)
            result.update(
                {
                    "status": "error",
                    "error": "Conversion failed unexpectedly. The file may be damaged or unsupported.",
                }
            )
        results.append(result)

    if not successful_files:
        shutil.rmtree(job_dir, ignore_errors=True)
        return jsonify({"job_id": None, "results": results, "success_count": 0})

    job = {
        "created": time.time(),
        "directory": job_dir,
        "files": successful_files,
        "zip_path": None,
    }
    with JOBS_LOCK:
        JOBS[job_id] = job

    return jsonify(
        {
            "job_id": job_id,
            "results": results,
            "success_count": len(successful_files),
            "download_all_url": f"/api/jobs/{job_id}/download-all"
            if len(successful_files) > 1
            else None,
        }
    )


def get_job(job_id: str) -> dict[str, Any]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job:
        abort(404, description="This conversion has expired or does not exist.")
    return job


@app.get("/api/jobs/<job_id>/files/<file_id>")
def download_file(job_id: str, file_id: str) -> ResponseReturnValue:
    job = get_job(job_id)
    record = next((item for item in job["files"] if item["id"] == file_id), None)
    if not record:
        abort(404, description="Converted file not found.")
    return send_file(record["path"], as_attachment=True, download_name=record["download_name"])


@app.get("/api/jobs/<job_id>/download-all")
def download_all(job_id: str) -> ResponseReturnValue:
    job = get_job(job_id)
    zip_path = job.get("zip_path")
    if not zip_path or not Path(zip_path).exists():
        zip_path = Path(job["directory"]) / "FileconverterAthome-batch.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as archive:
            for record in job["files"]:
                archive.write(record["path"], arcname=record["download_name"])
        job["zip_path"] = zip_path
    return send_file(zip_path, as_attachment=True, download_name="FileconverterAthome-batch.zip")


@app.delete("/api/jobs/<job_id>")
def delete_job(job_id: str) -> ResponseReturnValue:
    with JOBS_LOCK:
        job = JOBS.pop(job_id, None)
    if job:
        shutil.rmtree(job["directory"], ignore_errors=True)
    return ("", 204)


@app.errorhandler(RequestEntityTooLarge)
def batch_too_large(_error: RequestEntityTooLarge) -> ResponseReturnValue:
    return jsonify({"error": "This batch is larger than the 2 GB local limit."}), 413


@app.errorhandler(404)
def not_found(error: HTTPException) -> ResponseReturnValue:
    if request.path.startswith("/api/"):
        return jsonify({"error": error.description}), 404
    return error.get_response()


if __name__ == "__main__":
    port = int(os.environ.get("FILECONVERTERATHOME_PORT", "5174"))
    local_url = f"http://127.0.0.1:{port}"
    print(f"\n  FileconverterAthome is ready: {local_url}\n")
    server = make_server("127.0.0.1", port, app, threaded=True)
    BROWSER_SESSIONS.start(server.shutdown)
    if os.environ.get("FILECONVERTERATHOME_NO_BROWSER") != "1":
        Timer(1.0, lambda: webbrowser.open(local_url)).start()
    try:
        server.serve_forever()
    finally:
        BROWSER_SESSIONS.stop()
        server.server_close()
        cleanup_all_jobs()
