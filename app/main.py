"""FastAPI application for the desktop webview shell."""

from __future__ import annotations

import logging
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.datastructures import Headers
from starlette.middleware.sessions import SessionMiddleware
from starlette.staticfiles import NotModifiedResponse

from app.api.v1.convert.router import router as convert_router
from app.api.v1.settings.router import router as settings_router
from app.api.v1.setup.router import router as setup_router
from app.api.v1.wine.router import router as wine_router
from app.core.http_errors import (
    UNHANDLED_ERROR_MESSAGE,
    first_validation_error_message,
    http_exception_message,
    simple_html_error_page,
)
from app.core.paths import resource_root
from app.core.settings import APP_NAME, SESSION_KEY
from app.services.ui import TemplateRenderService
from app.version import VERSION

_log = logging.getLogger(__name__)

# Do not trust Windows mimetypes.guess_type — it often returns text/plain for .js.
_STATIC_TYPES = {
    ".css": "text/css",
    ".ico": "image/x-icon",
    ".js": "text/javascript",
    ".png": "image/png",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
}


class TypedStaticFiles(StaticFiles):
    """Serve static files with suffix MIME types, ignoring the OS registry."""

    def file_response(self, full_path, stat_result, scope, status_code: int = 200):
        suffix = os.path.splitext(str(full_path))[1].lower()
        response = FileResponse(
            full_path,
            status_code=status_code,
            stat_result=stat_result,
            media_type=_STATIC_TYPES.get(suffix, "application/octet-stream"),
        )
        if self.is_not_modified(response.headers, Headers(scope=scope)):
            return NotModifiedResponse(response.headers)
        return response


def _resolve_resource_dir(name: str) -> str:
    """Resolve the path for a resource directory (templates, static)."""
    path = resource_root() / name
    if not path.exists():
        path = resource_root() / "app" / name
    return str(path)


app = FastAPI(
    title=APP_NAME,
    version=VERSION,
    description="Avatar GLB → GMod playermodel pipeline (Setup / Convert / Settings)",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

app.add_middleware(SessionMiddleware, secret_key=SESSION_KEY)


def _render_htmx_error(request: Request, message: str) -> HTMLResponse:
    """Render an error without replacing the request's workspace target."""
    response = request.app.state.ui.render_error(request, message)
    response.headers["HX-Retarget"] = "#global-alerts"
    response.headers["HX-Reswap"] = "innerHTML"
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    message = http_exception_message(exc.detail)
    if request.headers.get("HX-Request") == "true":
        return _render_htmx_error(request, message)
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        back = request.headers.get("referer", "/")
        title = "Not allowed" if exc.status_code == 403 else "Invalid request"
        body = simple_html_error_page(title, message, back_url=back)
        return HTMLResponse(content=body, status_code=exc.status_code)
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(request: Request, exc: RequestValidationError):
    message = first_validation_error_message(exc.errors())
    if request.headers.get("HX-Request") == "true":
        return _render_htmx_error(request, message)
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        back = request.headers.get("referer", "/")
        body = simple_html_error_page("Invalid data", message, back_url=back)
        return HTMLResponse(content=body, status_code=422)
    return JSONResponse(
        status_code=422,
        content={"detail": jsonable_encoder(exc.errors())},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    _log.exception("Unhandled exception on %s %s", request.method, request.url.path)
    message = UNHANDLED_ERROR_MESSAGE
    if request.headers.get("HX-Request") == "true":
        return _render_htmx_error(request, message)
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        back = request.headers.get("referer", "/")
        body = simple_html_error_page("Unexpected error", message, back_url=back)
        return HTMLResponse(content=body, status_code=500)
    return JSONResponse(content={"detail": message}, status_code=500)


templates = Jinja2Templates(directory=_resolve_resource_dir("templates/html"))
app.mount("/static", TypedStaticFiles(directory=_resolve_resource_dir("static")), name="static")
ui_service = TemplateRenderService(templates)
app.state.ui = ui_service
app.include_router(setup_router)
app.include_router(convert_router)
app.include_router(settings_router)
app.include_router(wine_router)


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    """Render the home page."""
    return ui_service.render(
        request, "home.html", {"title": APP_NAME, "nav": "welcome"}
    )
