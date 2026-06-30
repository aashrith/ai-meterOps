from fastapi import APIRouter

from app.api.schemas import HealthResponse

router = APIRouter()


@router.get("/healthz", tags=["system"], response_model=HealthResponse)
def healthz() -> HealthResponse:
    return {"status": "ok"}
