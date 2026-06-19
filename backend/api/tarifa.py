from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import require_permiso
from core.database import get_db
from schemas.tarifa import TarifaConfigResponse, TarifaConfigUpdate
from services.pricing_service import obtener_tarifa

router = APIRouter(prefix="/tarifa", tags=["tarifa"])


@router.get("/", response_model=TarifaConfigResponse)
async def get_tarifa(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("tarifa", "read")),
):
    return await obtener_tarifa(db)


@router.patch("/", response_model=TarifaConfigResponse)
async def update_tarifa(
    payload: TarifaConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("tarifa", "write")),
):
    tarifa = await obtener_tarifa(db)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(tarifa, k, v)
    await db.commit()
    await db.refresh(tarifa)
    return tarifa
