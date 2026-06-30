from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.domain.errors import (
    GenerationFailed,
    MeteringStateInconsistent,
    QuotaConfigurationMissing,
    QuotaExceeded,
    RequestAlreadyExists,
    RequestInProgress,
)

app = FastAPI(
    title="AI Usage Metering and Quota Service",
    version="0.1.0",
)

app.include_router(router)


@app.exception_handler(QuotaConfigurationMissing)
def quota_missing_handler(_, exc: QuotaConfigurationMissing) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "quota configuration not found", "user_key": str(exc)})


@app.exception_handler(QuotaExceeded)
def quota_exceeded_handler(_, exc: QuotaExceeded) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc), "error": "quota_exceeded"})


@app.exception_handler(RequestAlreadyExists)
def request_exists_handler(_, exc: RequestAlreadyExists) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc), "error": "request_exists"})


@app.exception_handler(RequestInProgress)
def request_in_progress_handler(_, exc: RequestInProgress) -> JSONResponse:
    return JSONResponse(status_code=409, content={"detail": str(exc), "error": "request_in_progress"})


@app.exception_handler(GenerationFailed)
def generation_failed_handler(_, exc: GenerationFailed) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc), "error": "generation_failed"})


@app.exception_handler(MeteringStateInconsistent)
def metering_state_inconsistent_handler(_, exc: MeteringStateInconsistent) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": str(exc), "error": "inconsistent_state"})
