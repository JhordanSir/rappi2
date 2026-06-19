from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.dependencies import UserScope, get_mongo_db, get_scope, orden_en_alcance, require_permiso
from core.database import get_db
from core.pagination import paginate
from core.realtime import CANAL_STAFF, canal_cliente, publish
from models.asignaciones import Asignacion
from models.clientes import Cliente
from models.ordenes import Orden
from schemas.ordenes import OrdenCreate, OrdenResponse, OrdenUpdate
from services.geocoding import resolver_coords
from services.route_planner import autogenerar_ruta

router = APIRouter(prefix="/ordenes", tags=["ordenes"])


@router.get("/", response_model=list[OrdenResponse])
async def list_ordenes(
    response: Response,
    skip: int = 0,
    limit: int = Query(50, le=200),
    cliente_id: int | None = None,
    estado: str | None = None,
    q: str | None = Query(None, description="Búsqueda por ID o dirección (origen/destino)"),
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("ordenes", "read")),
):
    stmt = select(Orden)
    if not scope.ve_todo():
        # Cada usuario final solo ve sus propias ordenes (se ignora el filtro libre).
        if scope.cliente_id is not None:
            stmt = stmt.where(Orden.cliente_id == scope.cliente_id)
        elif scope.conductor_id is not None:
            stmt = stmt.where(
                Orden.id.in_(select(Asignacion.orden_id).where(Asignacion.conductor_id == scope.conductor_id))
            )
        else:
            stmt = stmt.where(False)
    elif cliente_id is not None:
        stmt = stmt.where(Orden.cliente_id == cliente_id)
    if estado is not None:
        stmt = stmt.where(Orden.estado == estado)
    if q:
        like = f"%{q.strip()}%"
        condiciones = [Orden.direccion_origen.ilike(like), Orden.direccion_destino.ilike(like)]
        termino = q.strip().lstrip("#")
        if termino.isdigit():
            condiciones.append(Orden.id == int(termino))
        stmt = stmt.where(or_(*condiciones))
    stmt = stmt.order_by(Orden.fecha_creacion.desc())
    return await paginate(db, stmt, response, skip, limit)


@router.post("/", response_model=OrdenResponse, status_code=status.HTTP_201_CREATED)
async def create_orden(
    payload: OrdenCreate,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("ordenes", "write")),
):
    data = payload.model_dump()
    # Un cliente solo puede crear ordenes a su propio nombre (se ignora el cliente_id enviado).
    if not scope.ve_todo() and scope.cliente_id is not None:
        data["cliente_id"] = scope.cliente_id
    cliente = await db.get(Cliente, data["cliente_id"])
    if cliente is None or not cliente.activo:
        raise HTTPException(status_code=400, detail="cliente_id invalido o inactivo")
    data["lat_origen"], data["lon_origen"] = await resolver_coords(
        data.get("direccion_origen"), data.get("lat_origen"), data.get("lon_origen")
    )
    data["lat_destino"], data["lon_destino"] = await resolver_coords(
        data.get("direccion_destino"), data.get("lat_destino"), data.get("lon_destino")
    )
    # El cliente paga por adelantado: su orden nace 'Pendiente de Pago' y solo se vuelve
    # despachable ('Pendiente') al confirmarse el pago. El staff crea órdenes ya despachables.
    es_cliente = not scope.ve_todo() and scope.cliente_id is not None
    estado_inicial = "Pendiente de Pago" if es_cliente else "Pendiente"
    orden = Orden(**data, estado=estado_inicial)
    db.add(orden)
    await db.commit()
    await db.refresh(orden)

    # Genera la ruta por calles automáticamente (best-effort, no bloquea la creación).
    oid = orden.id
    await autogenerar_ruta(db, orden, mongo_db)
    # Solo se avisa a la operación cuando la orden ya es despachable (no en 'Pendiente de Pago').
    if not es_cliente:
        await publish(
            CANAL_STAFF,
            {"tipo": "orden", "accion": "creada", "orden_id": oid, "cliente_id": orden.cliente_id, "estado": orden.estado},
        )
    return await db.get(Orden, oid)


@router.get("/{orden_id}", response_model=OrdenResponse)
async def get_orden(
    orden_id: int,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("ordenes", "read")),
):
    orden = await db.get(Orden, orden_id)
    if orden is None or not await orden_en_alcance(db, scope, orden):
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return orden


@router.patch("/{orden_id}", response_model=OrdenResponse)
async def update_orden(
    orden_id: int,
    payload: OrdenUpdate,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("ordenes", "write")),
):
    orden = await db.get(Orden, orden_id)
    if orden is None or not await orden_en_alcance(db, scope, orden):
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
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("ordenes", "delete")),
):
    orden = await db.get(Orden, orden_id)
    if orden is None or not await orden_en_alcance(db, scope, orden):
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    if orden.estado == "Cancelado":
        raise HTTPException(status_code=400, detail="La orden ya esta cancelada")
    orden.estado = "Cancelado"
    await db.commit()
    # Notifica el cambio de estado al dueño de la orden y a la operación.
    evento = {"tipo": "orden", "accion": "estado", "orden_id": orden.id, "estado": "Cancelado"}
    await publish(canal_cliente(orden.cliente_id), evento)
    await publish(CANAL_STAFF, evento)
