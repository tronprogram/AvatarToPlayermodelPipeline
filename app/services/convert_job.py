"""Background Convert job: export playermodel, then zip the addon."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from app.core.paths import data_dir
from app.services.addon_zip import zip_addon
from app.services.export_system import ExportSystemService
from app.services.playerlua import source_slug
from app.services.user_settings import load_settings, path_or_none

JobState = Literal["running", "succeeded", "failed"]


@dataclass
class ConvertJob:
    id: str
    state: JobState = "running"
    log: list[str] = field(default_factory=list)
    zip_path: Path | None = None
    slug: str = ""
    error: str = ""


_jobs: dict[str, ConvertJob] = {}
_lock = threading.Lock()


def get_job(job_id: str) -> ConvertJob | None:
    with _lock:
        return _jobs.get(job_id)


def start_convert(
    model_path: Path,
    *,
    display_name: str,
    gender: str,
    author: str,
    description: str,
) -> ConvertJob:
    job = ConvertJob(id=uuid.uuid4().hex, slug=source_slug(display_name))
    with _lock:
        _jobs[job.id] = job
    thread = threading.Thread(
        target=_run,
        args=(job.id, model_path, display_name, gender, author, description),
        daemon=True,
    )
    thread.start()
    return job


def _stage(job: ConvertJob, line: str) -> None:
    with _lock:
        job.log.append(line)


def _run(
    job_id: str,
    model_path: Path,
    display_name: str,
    gender: str,
    author: str,
    description: str,
) -> None:
    job = get_job(job_id)
    if job is None:
        return
    try:
        settings = load_settings()
        work = data_dir() / "export_test"
        zip_dir = path_or_none(settings.zip_dir) or (data_dir() / "zips")
        service = ExportSystemService(model_path)
        build = service.export_playermodel(
            work,
            display_name=display_name,
            gender="female" if gender == "female" else "male",
            author=author,
            description=description,
            on_stage=lambda line: _stage(job, line),
        )
        _stage(job, "pack       addon zip")
        dest = zip_dir / f"{build.identity.slug}.zip"
        zip_addon(build.addon.root, dest)
        with _lock:
            job.zip_path = dest
            job.slug = build.identity.slug
            job.state = "succeeded"
            job.log.append(f"ready      {dest}")
    except Exception as exc:
        with _lock:
            job.state = "failed"
            job.error = str(exc)
            job.log.append(f"error      {exc}")
