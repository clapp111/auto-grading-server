import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

import app.db.models
from app.api.exception_handlers import register_exception_handlers
from app.api.v1.router import api_router
from app.core.logging import logger
from app.core.metrics import metrics_app, observe_request, request_path


class MetricsAccessLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "GET /metrics" not in record.getMessage()


@asynccontextmanager
async def lifespan(_: FastAPI):
    logging.getLogger("uvicorn.access").addFilter(MetricsAccessLogFilter())
    yield


app = FastAPI(
    title="AI Assisted Grading API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/metrics", metrics_app)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    started_at = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        observe_request(request, 500, started_at)
        logger.exception(
            "Unhandled request error: method=%s path=%s",
            request.method,
            request_path(request),
        )
        raise

    elapsed_ms = (time.perf_counter() - started_at) * 1000
    path = request_path(request)

    if path.rstrip("/") != "/metrics":
        observe_request(request, response.status_code, started_at)
        log = logger.warning if response.status_code >= 400 else logger.info
        log(
            "HTTP request: method=%s path=%s status=%s duration_ms=%.2f",
            request.method,
            path,
            response.status_code,
            elapsed_ms,
        )
    return response


app.include_router(api_router, prefix="/api/v1")
register_exception_handlers(app)


@app.get("/health")
def health_check():
    return {"status": "ok"}
