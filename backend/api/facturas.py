from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.dependencies import require_permiso
from core.database import get_db
from models.ordenes import Factura, Orden
from schemas.facturas import FacturaCreate, FacturaResponse, FacturaUpdate, RucConsultaResponse
from services.sunat import RucInfo, RucInvalido, SunatNoDisponible, validar_ruc

router = APIRouter(tags=["facturas"])


async def _validar_ruc_factura(ruc: str | None) -> RucInfo | None:
    """Valida el RUC con SUNAT antes de registrar/validar una factura. Traduce las
    excepciones del servicio a códigos HTTP claros. RUC vacío => no valida."""
    if not ruc:
        return None
    try:
        return await validar_ruc(ruc)
    except RucInvalido as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except SunatNoDisponible as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"No se pudo validar el RUC con SUNAT: {exc}",
        )


@router.get("/facturas", response_model=list[FacturaResponse])
async def list_facturas(
    skip: int = 0,
    limit: int = Query(50, le=200),
    ruc: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("facturas", "read")),
):
    stmt = select(Factura)
    if ruc is not None:
        stmt = stmt.where(Factura.ruc == ruc)
    if desde is not None:
        stmt = stmt.where(Factura.fecha >= desde)
    if hasta is not None:
        stmt = stmt.where(Factura.fecha <= hasta)
    stmt = stmt.order_by(Factura.fecha.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.patch("/facturas/{factura_id}", response_model=FacturaResponse)
async def update_factura(
    factura_id: int,
    payload: FacturaUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("facturas", "write")),
):
    factura = await db.get(Factura, factura_id)
    if factura is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    cambios = payload.model_dump(exclude_unset=True)
    # Si se cambia el RUC, validarlo con SUNAT antes de persistir.
    if "ruc" in cambios:
        await _validar_ruc_factura(cambios["ruc"])
    for k, v in cambios.items():
        setattr(factura, k, v)
    await db.commit()
    await db.refresh(factura)
    return factura


@router.post("/ordenes/{orden_id}/facturas", response_model=FacturaResponse, status_code=status.HTTP_201_CREATED)
async def create_factura(
    orden_id: int,
    payload: FacturaCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("facturas", "write")),
):
    orden = await db.get(Orden, orden_id)
    if orden is None:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    # Validar el RUC con SUNAT antes de registrar la factura (req. fiscal).
    await _validar_ruc_factura(payload.ruc)
    factura = Factura(orden_id=orden_id, **payload.model_dump())
    db.add(factura)
    await db.commit()
    await db.refresh(factura)
    return factura


@router.get("/ordenes/{orden_id}/facturas", response_model=list[FacturaResponse])
async def list_facturas_orden(
    orden_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("facturas", "read")),
):
    result = await db.execute(select(Factura).where(Factura.orden_id == orden_id).order_by(Factura.fecha.desc()))
    return result.scalars().all()


@router.get("/facturas/validar-ruc/{ruc}", response_model=RucConsultaResponse, tags=["facturas"])
async def validar_ruc_endpoint(
    ruc: str,
    _: object = Depends(require_permiso("facturas", "write")),
):
    """Valida un RUC (formato/dígito + estado SUNAT si hay proveedor) sin crear factura.
    Útil para que la UI confirme el RUC y muestre la razón social antes de emitir."""
    info = await _validar_ruc_factura(ruc)
    return RucConsultaResponse(
        ruc=info.ruc,
        razon_social=info.razon_social,
        estado=info.estado,
        condicion=info.condicion,
        activo=info.activo,
        verificado_sunat=info.verificado_sunat,
    )


@router.get("/facturas/{factura_id}", response_model=FacturaResponse)
async def get_factura(
    factura_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("facturas", "read")),
):
    factura = await db.get(Factura, factura_id)
    if factura is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    return factura


@router.delete("/facturas/{factura_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_factura(
    factura_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("facturas", "delete")),
):
    factura = await db.get(Factura, factura_id)
    if factura is None:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    await db.delete(factura)
    await db.commit()
