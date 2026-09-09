import logging
import time
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import uuid4

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.api.v1.api import api_router
from app.core.config import get_settings
from app.core.database import dispose_engine

settings = get_settings()

# Setup structured logger
logger = logging.getLogger("app.access")
logging.basicConfig(level=logging.INFO if not settings.DEBUG else logging.DEBUG)


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Logs incoming requests with timing, path, status code, and correlation ID."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        correlation_id = request.headers.get("X-Correlation-ID", str(uuid4()))
        start_time = time.perf_counter()

        response = await call_next(request)

        process_time_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Process-Time-MS"] = str(process_time_ms)

        logger.info(
            "access_log",
            extra={
                "correlation_id": correlation_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "duration_ms": process_time_ms,
            },
        )
        return response


# Application Domain Exceptions
class EntityNotFoundError(Exception):
    def __init__(self, message: str) -> None:
        self.message = message


class LLMServiceException(Exception):
    def __init__(self, message: str) -> None:
        self.message = message


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages external service lifecycles across app startup and shutdown."""
    # Startup: Verify Redis connection pool
    app.state.redis_pool: ArqRedis = await create_pool(
        RedisSettings.from_dsn(str(settings.REDIS_URL))
    )
    yield
    # Shutdown: Cleanly close pools and database engine
    await app.state.redis_pool.close()
    await dispose_engine()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

# --- Middlewares ---
app.add_middleware(StructuredLoggingMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.ENVIRONMENT == "development" else ["https://app.yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Global Exception Handlers ---
@app.exception_handler(EntityNotFoundError)
async def entity_not_found_handler(request: Request, exc: EntityNotFoundError) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={"error": "Not Found", "detail": exc.message},
    )


@app.exception_handler(LLMServiceException)
async def llm_service_exception_handler(request: Request, exc: LLMServiceException) -> JSONResponse:
    logger.error("LLM Service failure on %s: %s", request.url.path, exc.message)
    return JSONResponse(
        status_code=status.HTTP_502_BAD_GATEWAY,
        content={"error": "Bad Gateway", "detail": "The AI provider failed to process the request."},
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server error: %s", exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal Server Error", "detail": "An unexpected error occurred."},
    )


# --- Include Routers ---
app.include_router(api_router, prefix="/api/v1")


@app.get("/healthz", tags=["System"])
async def health_check() -> dict[str, str]:
    return {"status": "ok", "environment": settings.ENVIRONMENT}