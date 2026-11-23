"""Сборка приложения. Импорт модуля не создаёт базу и не запускает сервер."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exception_handlers import request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.api import create_api_router
from app.repository import TicketNotFoundError, TicketRepository
from app.web import create_web_router

APP_DIR = Path(__file__).resolve().parent
DEFAULT_DATABASE_PATH = APP_DIR.parent / "data" / "tickets.sqlite3"


def create_app(database_path: Path | None = None, *, demo: bool = False) -> FastAPI:
    repository = TicketRepository(database_path or DEFAULT_DATABASE_PATH)
    templates = Jinja2Templates(directory=APP_DIR / "templates")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        repository.initialize()
        if demo:
            repository.seed_demo()
        yield

    app = FastAPI(
        title="Лаборатория · Заявки на обслуживание",
        description="Учебное приложение. Время создания заявок хранится в UTC.",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def check_origin(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Браузер не должен отправлять изменения с посторонней веб-страницы.
        origin = request.headers.get("origin")
        if (
            request.method not in {"GET", "HEAD", "OPTIONS"}
            and origin is not None
            and origin != str(request.base_url).rstrip("/")
        ):
            return JSONResponse({"detail": "Запрос с другого сайта запрещён."}, status_code=403)
        return await call_next(request)

    @app.exception_handler(TicketNotFoundError)
    async def ticket_not_found(request: Request, error: TicketNotFoundError) -> Response:
        return error_response(request, 404, "Заявка не найдена")

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, error: HTTPException) -> Response:
        if error.status_code == 404:
            return error_response(request, 404, "Страница не найдена")
        return JSONResponse(
            {"detail": error.detail}, status_code=error.status_code, headers=error.headers
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError) -> Response:
        if request.url.path.startswith("/api/"):
            return await request_validation_exception_handler(request, error)
        return error_response(request, 422, "Некорректный адрес или данные заявки")

    def error_response(request: Request, status_code: int, message: str) -> Response:
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": message}, status_code=status_code)
        return templates.TemplateResponse(
            request=request,
            name="error.html",
            context={"message": message, "status_code": status_code},
            status_code=status_code,
        )

    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost"])
    app.mount("/static", StaticFiles(directory=APP_DIR / "static"), name="static")
    app.include_router(create_api_router(repository))
    app.include_router(create_web_router(repository, templates))
    return app
