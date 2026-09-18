"""FastAPI application for the desktop webview shell."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

from app.api.v1.deps_wizard.router import router as deps_wizard_router
from app.api.v1.preview.router import router as preview_router
from app.core.csrf import CsrfError
from app.core.db import init_db
from app.core.http_errors import (
    CSRF_USER_MESSAGE,
    UNHANDLED_ERROR_MESSAGE,
    first_validation_error_message,
    http_exception_message,
    simple_html_error_page,
)
from app.core.paths import resource_root
from app.core.settings import (
    APP_NAME,
    SecurityConfigurationError,
    get_session_secret,
    is_production,
)
from app.services.ui import TemplateRenderService
from app.version import VERSION

_log = logging.getLogger(__name__)


def _resolve_resource_dir(name: str) -> str:
    """Resolve the path for a resource directory (templates, static)."""
    path = resource_root() / name
    if not path.exists():
        path = resource_root() / "app" / name
    return str(path)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create tables before serving requests."""
    init_db()
    yield


_docs_url = None if is_production() else "/docs"
_redoc_url = None if is_production() else "/redoc"
_openapi_url = None if is_production() else "/openapi.json"

app = FastAPI(
    title=APP_NAME,
    version=VERSION,
    description="Avatar GLB → GMod playermodel pipeline (deps wizard + preview shell)",
    lifespan=lifespan,
    docs_url=_docs_url,
    redoc_url=_redoc_url,
    openapi_url=_openapi_url,
)

app.add_middleware(SessionMiddleware, secret_key=get_session_secret())


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add baseline HTTP security headers to every response."""
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; "
        "frame-ancestors 'none'; "
        "base-uri 'self'; "
        "form-action 'self';"
    )
    return response


def _render_htmx_error(request: Request, message: str) -> HTMLResponse:
    """Render an error without replacing the request's workspace target."""
    response = request.app.state.ui.render_error(request, message)
    response.headers["HX-Retarget"] = "#global-alerts"
    response.headers["HX-Reswap"] = "innerHTML"
    return response


@app.exception_handler(CsrfError)
async def csrf_error_exception_handler(request: Request, exc: CsrfError):
    message = CSRF_USER_MESSAGE
    if request.headers.get("HX-Request") == "true":
        return _render_htmx_error(request, message)
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        body = simple_html_error_page("Session expired", message)
        return HTMLResponse(content=body, status_code=403)
    return JSONResponse(content={"detail": message}, status_code=403)


@app.exception_handler(SecurityConfigurationError)
async def security_configuration_error_handler(
    request: Request, exc: SecurityConfigurationError
):
    _log.error("Security configuration error: %s", exc)
    message = "The app could not start because of a configuration error."
    if request.headers.get("HX-Request") == "true":
        return _render_htmx_error(request, message)
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        body = simple_html_error_page("Configuration error", message)
        return HTMLResponse(content=body, status_code=500)
    return JSONResponse(content={"detail": message}, status_code=500)


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
app.mount("/static", StaticFiles(directory=_resolve_resource_dir("static")), name="static")
ui_service = TemplateRenderService(templates)
app.state.ui = ui_service
app.include_router(deps_wizard_router)
app.include_router(preview_router)


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    """Liveness probe used by the desktop launcher wait loop."""
    return {"ok": True}


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    """Render the home page."""
    return ui_service.render(request, "home.html", {"title": APP_NAME})
