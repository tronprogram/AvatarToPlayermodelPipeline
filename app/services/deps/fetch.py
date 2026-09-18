"""HTTP downloads for wizard archives."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse

import requests

from app.core.http import filename_from_content_disposition

_DOWNLOAD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
}


def _headers_for(url: str) -> dict[str, str]:
    headers = dict(_DOWNLOAD_HEADERS)
    if "steamreview.org" in url:
        headers["Referer"] = "http://steamreview.org/BlenderSourceTools/"
    return headers


def _filename_from_response(response: requests.Response) -> str:
    name = filename_from_content_disposition(response.headers.get("Content-Disposition"))
    if name:
        return name
    path = urlparse(response.url).path.rstrip("/")
    name = Path(unquote(path)).name
    if name and name not in {"download", "download.php"}:
        return name
    return "download.bin"


def download_archive(dest: Path, url: str) -> str:
    """Stream one archive to dest. Blocking — run via asyncio.to_thread."""
    with requests.get(
        url,
        headers=_headers_for(url),
        stream=True,
        timeout=(15, 300),
        allow_redirects=True,
    ) as response:
        response.raise_for_status()
        filename = _filename_from_response(response)
        path = dest / filename
        with path.open("wb") as handle:
            for chunk in response.iter_content(chunk_size=256 * 1024):
                if chunk:
                    handle.write(chunk)
        return filename
