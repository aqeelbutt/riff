"""GET /presets — the style registry both surfaces render from."""
from fastapi import APIRouter

from app.services.presets import all_presets

router = APIRouter(prefix="/presets", tags=["presets"])


@router.get("")
async def presets() -> dict:
    return all_presets()
