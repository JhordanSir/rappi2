from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from decimal import Decimal

from api.dependencies import UserScope, get_mongo_db, get_scope, orden_en_alcance, require_permiso
from core.database import get_db
from core.pagination import paginate
from core.realtime import CANAL_STAFF, canal_cliente, publish
from models.asignaciones import Asignacion
from models.clientes import Cliente
from models.ordenes import Orden
from schemas.ordenes import (
    CotizacionResponse,
    CotizarRequest,
    OrdenCreate,
    OrdenResponse,
    OrdenUpdate,
)
from services.geocoding import resolver_coords
from services.pricing_service import cotizar_tramo
from services.route_planner import autogenerar_ruta

router = APIRouter(prefix="/ordenes", tags=["ordenes"])


async def _calcular_total(db: AsyncSession, orden_data: dict) -> Decimal | None:
    """Calcula el total server-side de un tramo. None si faltan coordenadas."""
    if None in (
        orden_data.get("lat_origen"), orden_data.get("lon_origen"),
        orden_data.get("lat_destino"), orden_data.get("lon_destino"),
    ):
        return None
    cot = await cotizar_tramo(
        db,
        float(orden_data["lon_origen"]), float(orden_data["lat_origen"]),
        float(orden_data["lon_destino"]), float(orden_data["lat_destino"]),
        peso_kg=orden_data.get("peso_kg"),
        largo_cm=orden_data.get("largo_cm"),
        ancho_cm=orden_data.get("ancho_cm"),
        alto_cm=orden_data.get("alto_cm"),
        nivel_servicio=orden_data.get("nivel_servicio", "estandar"),
        cuando=orden_data.get("programado_para"),
    )
    return Decimal(str(cot["total"]))


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
    # El ajuste de precio solo lo aplica el staff; el cliente nunca fija ni ajusta el precio.
    ajuste_monto = data.pop("ajuste_monto", None)
    ajuste_motivo = data.pop("ajuste_motivo", None)
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

    # Precio calculado por el servidor (nunca confiamos en un total del cliente).
    try:
        total = await _calcular_total(db, data)
    except Exception as exc:  # noqa: BLE001 - OSRM puede fallar; no bloquea la creación
        import logging
        logging.getLogger(__name__).warning("No se pudo calcular precio de la orden: %s", exc)
        total = None
    data["total"] = total
    # Ajuste manual de staff: queda registrado (monto, motivo, quién) y modifica el total.
    if scope.ve_todo() and ajuste_monto is not None:
        data["ajuste_monto"] = ajuste_monto
        data["ajuste_motivo"] = ajuste_motivo
        data["ajuste_por"] = scope.user.id
        if total is not None:
            data["total"] = max(Decimal("0"), total + Decimal(str(ajuste_monto)))

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


@router.post("/cotizar", response_model=CotizacionResponse)
async def cotizar_orden(
    payload: CotizarRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("ordenes", "read")),
):
    """Devuelve la cotización (precio calculado) de un envío sin crearlo, para
    mostrarla en vivo al cliente antes de pagar."""
    try:
        return await cotizar_tramo(
            db,
            payload.lon_origen, payload.lat_origen,
            payload.lon_destino, payload.lat_destino,
            peso_kg=payload.peso_kg, largo_cm=payload.largo_cm,
            ancho_cm=payload.ancho_cm, alto_cm=payload.alto_cm,
            nivel_servicio=payload.nivel_servicio,
            cuando=payload.programado_para,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"No se pudo cotizar la ruta: {exc}")


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
    # El ajuste de precio solo lo aplica el staff.
    ajuste_monto = update.pop("ajuste_monto", None)
    ajuste_motivo = update.pop("ajuste_motivo", None)
    # Re-geocodificar si cambia una direccion y no se enviaron coords explicitas.
    if "direccion_origen" in update and update.get("lat_origen") is None and update.get("lon_origen") is None:
        update["lat_origen"], update["lon_origen"] = await resolver_coords(update["direccion_origen"], None, None)
    if "direccion_destino" in update and update.get("lat_destino") is None and update.get("lon_destino") is None:
        update["lat_destino"], update["lon_destino"] = await resolver_coords(update["direccion_destino"], None, None)
    for k, v in update.items():
        setattr(orden, k, v)

    # Recalcular el precio si cambió algo que lo afecta (coords, paquete, servicio, horario)
    # o si el staff aplica/ajusta el override.
    afecta_precio = any(
        c in update for c in (
            "lat_origen", "lon_origen", "lat_destino", "lon_destino",
            "peso_kg", "largo_cm", "ancho_cm", "alto_cm", "nivel_servicio", "programado_para",
        )
    )
    if afecta_precio or (scope.ve_todo() and ajuste_monto is not None):
        try:
            base = await _calcular_total(db, {
                "lat_origen": orden.lat_origen, "lon_origen": orden.lon_origen,
                "lat_destino": orden.lat_destino, "lon_destino": orden.lon_destino,
                "peso_kg": orden.peso_kg, "largo_cm": orden.largo_cm,
                "ancho_cm": orden.ancho_cm, "alto_cm": orden.alto_cm,
                "nivel_servicio": orden.nivel_servicio, "programado_para": orden.programado_para,
            })
        except Exception:  # noqa: BLE001
            base = orden.total
        if scope.ve_todo() and ajuste_monto is not None:
            orden.ajuste_monto = ajuste_monto
            orden.ajuste_motivo = ajuste_motivo
            orden.ajuste_por = scope.user.id
        ajuste = Decimal(str(orden.ajuste_monto)) if orden.ajuste_monto is not None else Decimal("0")
        orden.total = max(Decimal("0"), (base or Decimal("0")) + ajuste) if base is not None else None

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
