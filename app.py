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
from collections.abc import Iterable
from pathlib import Path
from threading import Lock, RLock, Timer
from typing import Any, cast

from flask import Flask, abort, jsonify, render_template, request, send_file
from flask.typing import ResponseReturnValue
from werkzeug.exceptions import HTTPException, RequestEntityTooLarge
from werkzeug.serving import make_server
from werkzeug.wsgi import ClosingIterator

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
app.config["TRUSTED_HOSTS"] = ["127.0.0.1", "localhost", "[::1]"]

converter = ConversionManager()
BROWSER_SESSIONS = BrowserSessionManager()
JOBS: dict[str, dict[str, Any]] = {}
JOBS_LOCK = RLock()
CONVERSION_SLOT = Lock()
MAX_FILES = 50
JOB_TTL_SECONDS = 2 * 60 * 60


def cleanup_expired_jobs() -> None:
    cutoff = time.time() - JOB_TTL_SECONDS
    expired: list[dict] = []
    with JOBS_LOCK:
        for job_id, job in list(JOBS.items()):
            if job["status"] != "running" and not job["downloads"] and job["created"] < cutoff:
                expired.append(JOBS.pop(job_id))
    for job in expired:
        shutil.rmtree(job["directory"], ignore_errors=True)


def cleanup_all_jobs() -> None:
    """Remove all temporary conversion data during a normal process exit."""
    with JOBS_LOCK:
        jobs = []
        for job_id, job in list(JOBS.items()):
            job["deleted"] = True
            if job["status"] != "running" and not job["downloads"]:
                jobs.append(JOBS.pop(job_id))
    for job in jobs:
        shutil.rmtree(job["directory"], ignore_errors=True)


atexit.register(cleanup_all_jobs)


@app.before_request
def maintain_job_store() -> None:
    if request.path.startswith("/api/") and request.method not in {"GET", "HEAD", "OPTIONS"}:
        origin = request.headers.get("Origin")
        if origin and origin != request.host_url.rstrip("/"):
            abort(403, description="Requests must come from the local converter page.")
    cleanup_expired_jobs()


@app.after_request
def prevent_stale_responses(response: Any) -> Any:
    if request.path == "/" or request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


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
    if not CONVERSION_SLOT.acquire(blocking=False):
        return (
            jsonify({"error": "Another batch is converting. Please wait and try again."}),
            429,
            {"Retry-After": "3"},
        )
    BROWSER_SESSIONS.begin_activity()
    try:
        return process_batch()
    finally:
        BROWSER_SESSIONS.end_activity()
        CONVERSION_SLOT.release()


def process_batch() -> ResponseReturnValue:
    uploads = request.files.getlist("files")
    targets = request.form.getlist("targets")

    if not uploads:
        return jsonify({"error": "Choose at least one file to convert."}), 400
    if len(uploads) > MAX_FILES:
        return jsonify({"error": f"A batch can contain at most {MAX_FILES} files."}), 400
    if len(targets) != len(uploads):
        return jsonify({"error": "Every file needs an output format."}), 400

    try:
        job_id = uuid.UUID(request.headers.get("X-Conversion-ID", uuid.uuid4().hex)).hex
    except ValueError:
        return jsonify({"error": "Invalid conversion identifier."}), 400
    with JOBS_LOCK:
        if job_id in JOBS:
            return jsonify({"error": "This batch identifier has already been used."}), 409
    job_dir = Path(tempfile.mkdtemp(prefix=f"fileconverterathome-{job_id[:8]}-"))
    results: list[dict[str, Any]] = []
    successful_files: list[dict[str, Any]] = []
    used_names: set[str] = set()
    job: dict[str, Any] = {
        "created": time.time(),
        "directory": job_dir,
        "files": successful_files,
        "results": results,
        "zip_path": None,
        "zip_lock": Lock(),
        "downloads": 0,
        "deleted": False,
        "status": "running",
        "total": len(uploads),
        "completed": 0,
        "current_file": None,
    }
    with JOBS_LOCK:
        JOBS[job_id] = job

    for upload, target in zip(uploads, targets, strict=True):
        original_name = upload.filename or "untitled"
        result: dict[str, Any] = {"input_name": original_name}
        source_path: Path | None = None
        output_path: Path | None = None
        with JOBS_LOCK:
            job["current_file"] = original_name
        try:
            source_format = converter.detect_format(original_name)
            target = target.lower().strip().lstrip(".")
            converter.validate_conversion(source_format, target)

            source_path = job_dir / f"source-{uuid.uuid4().hex}.{source_format}"
            upload.save(source_path)
            if not source_path.exists() or source_path.stat().st_size == 0:
                raise ConversionError("The uploaded file is empty.")

            output_path = job_dir / f"output-{uuid.uuid4().hex}.{target}"
            note = converter.convert(source_path, source_format, output_path, target)
            if not output_path.exists() or output_path.stat().st_size == 0:
                raise ConversionError("The converter did not produce a usable file.")

            file_id = uuid.uuid4().hex
            download_name = output_filename(original_name, target, used_names)
            file_record = {
                "id": file_id,
                "path": output_path,
                "download_name": download_name,
            }
            with JOBS_LOCK:
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
        finally:
            upload.close()
            for work_path in (
                source_path,
                output_path if result.get("status") != "success" else None,
            ):
                if work_path:
                    try:
                        work_path.unlink(missing_ok=True)
                    except OSError:
                        app.logger.warning("Temporary file cleanup deferred for %s", work_path)
        with JOBS_LOCK:
            results.append(result)
            job["completed"] = len(results)

    with JOBS_LOCK:
        job["status"] = "complete"
        job["current_file"] = None
        job["created"] = time.time()

    if not successful_files:
        shutil.rmtree(job_dir, ignore_errors=True)
    return jsonify(job_payload(job_id, job))


def job_payload(job_id: str, job: dict[str, Any]) -> dict[str, Any]:
    """Return a snapshot without exposing temporary paths or mutable lists."""
    with JOBS_LOCK:
        return {
            "job_id": job_id,
            "status": job["status"],
            "total": job["total"],
            "completed": job["completed"],
            "current_file": job["current_file"],
            "results": list(job["results"]),
            "success_count": len(job["files"]),
            "download_all_url": f"/api/jobs/{job_id}/download-all"
            if len(job["files"]) > 1
            else None,
        }


def get_job(job_id: str) -> dict[str, Any]:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
    if not job or job["deleted"]:
        abort(404, description="This conversion has expired or does not exist.")
    return job


@app.get("/api/jobs/<job_id>")
def job_status(job_id: str) -> ResponseReturnValue:
    return jsonify(job_payload(job_id, get_job(job_id)))


def acquire_download(job_id: str) -> dict[str, Any]:
    with JOBS_LOCK:
        job = get_job(job_id)
        if job["status"] != "complete":
            abort(409, description="This batch is still converting.")
        if not job["files"]:
            abort(404, description="This batch has no converted files.")
        job["downloads"] += 1
        BROWSER_SESSIONS.begin_activity()
        return job


def release_download(job_id: str, job: dict[str, Any]) -> None:
    with JOBS_LOCK:
        job["downloads"] -= 1
        remove = job["deleted"] and not job["downloads"]
        if remove:
            JOBS.pop(job_id, None)
    if remove:
        shutil.rmtree(job["directory"], ignore_errors=True)
    BROWSER_SESSIONS.end_activity()


def stream_download(job_id: str, job: dict[str, Any], path: Path, name: str) -> ResponseReturnValue:
    response = send_file(path, as_attachment=True, download_name=name)
    response.response = ClosingIterator(
        cast(Iterable[bytes], response.response), lambda: release_download(job_id, job)
    )
    return response


@app.get("/api/jobs/<job_id>/files/<file_id>")
def download_file(job_id: str, file_id: str) -> ResponseReturnValue:
    job = acquire_download(job_id)
    try:
        record = next((item for item in job["files"] if item["id"] == file_id), None)
        if not record:
            abort(404, description="Converted file not found.")
        return stream_download(job_id, job, record["path"], record["download_name"])
    except Exception:
        release_download(job_id, job)
        raise


@app.get("/api/jobs/<job_id>/download-all")
def download_all(job_id: str) -> ResponseReturnValue:
    job = acquire_download(job_id)
    try:
        with job["zip_lock"]:
            zip_path = Path(job["directory"]) / "FileconverterAthome-batch.zip"
            if not job["zip_path"]:
                temporary_zip = zip_path.with_suffix(".zip.part")
                try:
                    with zipfile.ZipFile(
                        temporary_zip, "w", compression=zipfile.ZIP_STORED
                    ) as archive:
                        for record in job["files"]:
                            archive.write(record["path"], arcname=record["download_name"])
                    temporary_zip.replace(zip_path)
                    job["zip_path"] = zip_path
                finally:
                    temporary_zip.unlink(missing_ok=True)
        return stream_download(job_id, job, zip_path, zip_path.name)
    except Exception:
        release_download(job_id, job)
        raise


@app.delete("/api/jobs/<job_id>")
def delete_job(job_id: str) -> ResponseReturnValue:
    with JOBS_LOCK:
        job = JOBS.get(job_id)
        if job:
            if job["status"] == "running":
                abort(409, description="Wait for this batch to finish before clearing it.")
            job["deleted"] = True
            if not job["downloads"]:
                JOBS.pop(job_id, None)
    if job and not job["downloads"]:
        shutil.rmtree(job["directory"], ignore_errors=True)
    return ("", 204)


@app.errorhandler(RequestEntityTooLarge)
def batch_too_large(_error: RequestEntityTooLarge) -> ResponseReturnValue:
    return jsonify({"error": "This batch is larger than the 2 GB local limit."}), 413


@app.errorhandler(HTTPException)
def not_found(error: HTTPException) -> ResponseReturnValue:
    if request.path.startswith("/api/"):
        return jsonify({"error": error.description}), error.code or 500
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
