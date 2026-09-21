"""Wizard phase machine: check, fetch, extract, then GMod tools."""

from __future__ import annotations

import asyncio
from typing import Literal, NotRequired, TypedDict

from app.core.paths import data_dir
from app.services.deps.catalog import dependency_links, load_catalog
from app.services.deps.detect import (
    any_executable_in_dir,
    blender_root,
    downloaded_archives,
    find_hlmvplusplus,
    find_modified_compiler,
    find_source_tools,
    gmod_app_installed,
    gmod_tools_present,
    gmod_tools_root,
    install_path,
    named_executable_found,
)
from app.services.deps.extract import (
    extract_install,
    extract_modified_compiler,
    extract_hlmvplusplus,
)
from app.services.deps.fetch import download_archive
from app.services.deps.steamcmd import DownloadStatus, find_steamcmd, gmod_download

Phase = Literal["ready", "needs_download", "needs_extract", "needs_manual"]


class DependencyStatus(TypedDict):
    phase: Phase
    ok: bool
    needs_download: bool
    needs_extract: bool
    needs_manual: bool
    paths: dict[str, str | None]
    archives: dict[str, str | None]
    executables: dict[str, bool | None]
    missing: list[str]
    missing_archives: list[str]
    missing_manual: list[str]
    download: DownloadStatus


class FetchResult(DependencyStatus):
    downloaded: list[str]
    error: NotRequired[str]


class ExtractResult(DependencyStatus):
    extracted: list[str]
    error: NotRequired[str]


def _build_status(
    *,
    paths: dict[str, str | None],
    archives: dict[str, str | None],
    executables: dict[str, bool | None],
    missing: list[str],
) -> DependencyStatus:
    catalog = load_catalog()
    missing_archives = [name for name, filename in archives.items() if not filename]
    archive_tree_ready = not any(
        install_key in missing for install_key in catalog.archive_installs.values()
    )
    missing_manual = [key for key in catalog.manual_installs if key in missing]
    archives_ready = not missing_archives
    install_ready = not missing

    if install_ready:
        phase: Phase = "ready"
    elif archives_ready and not archive_tree_ready:
        phase = "needs_extract"
    elif not archive_tree_ready:
        phase = "needs_download"
    else:
        phase = "needs_manual"

    return {
        "phase": phase,
        "ok": phase == "ready",
        "needs_download": phase == "needs_download",
        "needs_extract": phase == "needs_extract",
        "needs_manual": phase == "needs_manual",
        "paths": paths,
        "archives": archives,
        "executables": executables,
        "missing": missing,
        "missing_archives": missing_archives,
        "missing_manual": missing_manual,
        "download": gmod_download.snapshot(),
    }


class DepsWizardService:
    """Advance install phases. Tooling lives in app.services.deps."""

    def __init__(self, system_type: str, system_arch: str):
        self.system_type = system_type
        self.system_arch = system_arch

    def check_dependencies(self) -> DependencyStatus:
        project_path = data_dir()
        archives = downloaded_archives(
            project_path,
            dependency_links(self.system_type, self.system_arch),
        )
        contents: dict[str, str | None] = {}
        missing: list[str] = []
        executables: dict[str, bool | None] = {}

        for program, (executable, dir_name, check_executable) in load_catalog().directories.items():
            if program == "blender_addons":
                found_addon = find_source_tools(blender_root(project_path))
                if found_addon:
                    contents[program] = found_addon.relative_to(project_path).as_posix()
                else:
                    contents[program] = None
                    missing.append(program)
                executables[program] = None
                continue

            subdir = project_path / dir_name
            if subdir.exists():
                contents[program] = dir_name
            else:
                contents[program] = None
                missing.append(program)

            if not check_executable:
                executables[program] = None
                continue

            if program == "steamcmd":
                found = find_steamcmd(subdir) is not None
            elif program == "compiler":
                found = find_modified_compiler(project_path) is not None
            elif program == "hlmvplusplus":
                found = find_hlmvplusplus(project_path) is not None
            elif executable:
                found = named_executable_found(executable, subdir)
            elif program == "gmod_tools":
                found = gmod_tools_present(subdir)
            else:
                found = any_executable_in_dir(subdir)

            executables[program] = found
            if not found and program not in missing:
                missing.append(program)

        return _build_status(
            paths=contents,
            archives=archives,
            executables=executables,
            missing=missing,
        )

    async def fetch_dependencies(self) -> FetchResult:
        status = self.check_dependencies()
        if not status["needs_download"]:
            return {**status, "downloaded": []}

        links = dependency_links(self.system_type, self.system_arch)
        dest = data_dir()
        pending = {
            name: url
            for name, url in links.items()
            if name in status["missing_archives"]
        }
        try:
            saved = await asyncio.gather(
                *[
                    asyncio.to_thread(download_archive, dest, url)
                    for url in pending.values()
                ]
            )
            return {**self.check_dependencies(), "downloaded": list(saved)}
        except Exception as exc:
            return {**status, "downloaded": [], "error": str(exc)}

    async def extract_dependencies(self) -> ExtractResult:
        status = self.check_dependencies()
        if not status["needs_extract"]:
            return {**status, "extracted": []}

        dest = data_dir()
        pending = [
            key
            for key, install_key in load_catalog().archive_installs.items()
            if status["archives"].get(key) and install_key in status["missing"]
        ]
        pending.sort(key=lambda key: 0 if key == "blender" else 1)
        extracted: list[str] = []
        try:
            for key in pending:
                filename = status["archives"][key]
                if not filename:
                    continue
                if key == "compiler":
                    await asyncio.to_thread(
                        extract_modified_compiler, dest / filename, dest
                    )
                elif key == "hlmvplusplus":
                    await asyncio.to_thread(
                        extract_hlmvplusplus, dest / filename, dest
                    )
                else:
                    await asyncio.to_thread(
                        extract_install,
                        dest / filename,
                        install_path(dest, key),
                        unwrap=(key != "sourcetools"),
                    )
                extracted.append(key)
            return {**self.check_dependencies(), "extracted": extracted}
        except Exception as exc:
            return {**status, "extracted": extracted, "error": str(exc)}

    def gmod_tools_status(self, *, start: bool = False) -> DependencyStatus:
        """Return SteamCMD progress. POST starts the job only if 4020 is missing."""
        status = self.check_dependencies()
        if start and status["needs_manual"] and not gmod_app_installed(gmod_tools_root(data_dir())):
            snap = status["download"]
            if snap["state"] in ("idle", "failed"):
                gmod_download.start(data_dir())
        return self.check_dependencies()
