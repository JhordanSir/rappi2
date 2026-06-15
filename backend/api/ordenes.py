from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.dependencies import get_mongo_db, require_permiso
from core.database import get_db
from models.clientes import Cliente
from models.ordenes import Orden
from schemas.ordenes import OrdenCreate, OrdenResponse, OrdenUpdate
from services.geocoding import resolver_coords
from services.route_planner import autogenerar_ruta

router = APIRouter(prefix="/ordenes", tags=["ordenes"])


@router.get("/", response_model=list[OrdenResponse])
async def list_ordenes(
    skip: int = 0,
    limit: int = Query(50, le=200),
    cliente_id: int | None = None,
    estado: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("ordenes", "read")),
):
    stmt = select(Orden)
    if cliente_id is not None:
        stmt = stmt.where(Orden.cliente_id == cliente_id)
    if estado is not None:
        stmt = stmt.where(Orden.estado == estado)
    stmt = stmt.order_by(Orden.fecha_creacion.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=OrdenResponse, status_code=status.HTTP_201_CREATED)
async def create_orden(
    payload: OrdenCreate,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("ordenes", "write")),
):
    cliente = await db.get(Cliente, payload.cliente_id)
    if cliente is None or not cliente.activo:
        raise HTTPException(status_code=400, detail="cliente_id invalido o inactivo")
    data = payload.model_dump()
    data["lat_origen"], data["lon_origen"] = await resolver_coords(
        data.get("direccion_origen"), data.get("lat_origen"), data.get("lon_origen")
    )
    data["lat_destino"], data["lon_destino"] = await resolver_coords(
        data.get("direccion_destino"), data.get("lat_destino"), data.get("lon_destino")
    )
    orden = Orden(**data, estado="Pendiente")
    db.add(orden)
    await db.commit()
    await db.refresh(orden)

    # Genera la ruta por calles automáticamente (best-effort, no bloquea la creación).
    oid = orden.id
    await autogenerar_ruta(db, orden, mongo_db)
    return await db.get(Orden, oid)


@router.get("/{orden_id}", response_model=OrdenResponse)
async def get_orden(
    orden_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("ordenes", "read")),
):
    orden = await db.get(Orden, orden_id)
    if orden is None:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return orden


@router.patch("/{orden_id}", response_model=OrdenResponse)
async def update_orden(
    orden_id: int,
    payload: OrdenUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("ordenes", "write")),
):
    orden = await db.get(Orden, orden_id)
    if orden is None:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    update = payload.model_dump(exclude_unset=True)
    # Re-geocodificar si cambia una direccion y no se enviaron coords explicitas.
    if "direccion_origen" in update and update.get("lat_origen") is None and update.get("lon_origen") is None:
        update["lat_origen"], update["lon_origen"] = await resolver_coords(update["direccion_origen"], None, None)
    if "direccion_destino" in update and update.get("lat_destino") is None and update.get("lon_destino") is None:
        update["lat_destino"], update["lon_destino"] = await resolver_coords(update["direccion_destino"], None, None)
    for k, v in update.items():
        setattr(orden, k, v)
    await db.commit()
    await db.refresh(orden)
    return orden


@router.delete("/{orden_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_orden(
    orden_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("ordenes", "delete")),
):
    orden = await db.get(Orden, orden_id)
    if orden is None:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    if orden.estado == "Cancelado":
        raise HTTPException(status_code=400, detail="La orden ya esta cancelada")
    orden.estado = "Cancelado"
    await db.commit()
