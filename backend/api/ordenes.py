from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from decimal import Decimal

from api.dependencies import UserScope, get_mongo_db, get_scope, orden_en_alcance, require_permiso
from core.database import get_db
from core.estados import TRANSICIONES_ORDEN, validar_transicion
from core.pagination import ordenar, paginate
from core.realtime import CANAL_STAFF, canal_cliente, publish
from models.asignaciones import Asignacion, asignacion_ordenes
from models.clientes import Cliente
from models.conductores import Conductor
from models.destinos import Destino
from models.ordenes import Orden
from schemas.ordenes import (
    CotizacionResponse,
    CotizarRequest,
    DestinoIn,
    DestinoUpdate,
    OrdenCreate,
    OrdenResponse,
    OrdenUpdate,
)
from services.geocoding import resolver_coords
from services.pricing_service import cotizar_orden as cotizar_orden_precio
from services.route_planner import autogenerar_ruta

router = APIRouter(prefix="/ordenes", tags=["ordenes"])

# Campos ordenables desde la UI (clic en cabecera). Whitelist: ver core/pagination.ordenar.
_ORDENABLES = {
    "id": Orden.id,
    "estado": Orden.estado,
    "total": Orden.total,
    "fecha_creacion": Orden.fecha_creacion,
    "cliente_id": Orden.cliente_id,
    "nivel_servicio": Orden.nivel_servicio,
}


async def _get_orden_full(db: AsyncSession, orden_id: int) -> Orden | None:
    """Carga una orden con sus destinos (necesario para serializar OrdenResponse)."""
    return (
        await db.execute(
            select(Orden).options(selectinload(Orden.destinos)).where(Orden.id == orden_id)
        )
    ).scalar_one_or_none()


def _normalizar_destinos(data: dict) -> list[dict]:
    """Devuelve la lista de destinos: los explícitos o uno construido desde los
    campos legacy de destino único. Cada dict lleva dirección, coords y paquete."""
    if data.get("destinos"):
        return [dict(d) for d in data["destinos"]]
    return [{
        "direccion": data.get("direccion_destino"),
        "distrito": data.get("distrito_destino"),
        "lat": data.get("lat_destino"),
        "lon": data.get("lon_destino"),
        "peso_kg": data.get("peso_kg"),
        "largo_cm": data.get("largo_cm"),
        "ancho_cm": data.get("ancho_cm"),
        "alto_cm": data.get("alto_cm"),
        "nombre_destinatario": None,
    }]


async def _cotizar_destinos(db: AsyncSession, origen_lon, origen_lat, destinos: list[dict], nivel: str, cuando) -> dict | None:
    """Cotiza la orden (suma de tramos). None si faltan coords de origen o destinos."""
    if origen_lon is None or origen_lat is None:
        return None
    listos = [d for d in destinos if d.get("lon") is not None and d.get("lat") is not None]
    if not listos:
        return None
    return await cotizar_orden_precio(db, float(origen_lon), float(origen_lat), listos, nivel_servicio=nivel, cuando=cuando)


@router.get("/", response_model=list[OrdenResponse])
async def list_ordenes(
    response: Response,
    skip: int = 0,
    limit: int = Query(50, le=200),
    cliente_id: int | None = None,
    estado: str | None = None,
    q: str | None = Query(None, description="Búsqueda por ID, dirección o cliente (nombre/email)"),
    desde: datetime | None = Query(None, description="fecha_creacion >= desde"),
    hasta: datetime | None = Query(None, description="fecha_creacion <= hasta"),
    nivel_servicio: str | None = None,
    distrito: str | None = Query(None, description="Distrito de origen O destino (parcial)"),
    orden_por: str | None = Query(None, description="Campo de ordenamiento (cabecera)"),
    direccion: str | None = Query(None, alias="dir", description="asc | desc"),
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("ordenes", "read")),
):
    stmt = select(Orden).options(selectinload(Orden.destinos))
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
    if desde is not None:
        stmt = stmt.where(Orden.fecha_creacion >= desde)
    if hasta is not None:
        stmt = stmt.where(Orden.fecha_creacion <= hasta)
    if nivel_servicio is not None:
        stmt = stmt.where(Orden.nivel_servicio == nivel_servicio)
    if distrito:
        d = f"%{distrito.strip()}%"
        stmt = stmt.where(or_(Orden.distrito_origen.ilike(d), Orden.distrito_destino.ilike(d)))
    if q:
        like = f"%{q.strip()}%"
        condiciones = [
            Orden.direccion_origen.ilike(like),
            Orden.direccion_destino.ilike(like),
            # También por datos del cliente (nombre/email) — el staff busca así.
            Orden.cliente_id.in_(
                select(Cliente.id).where(or_(Cliente.nombre.ilike(like), Cliente.email.ilike(like)))
            ),
        ]
        termino = q.strip().lstrip("#")
        if termino.isdigit():
            condiciones.append(Orden.id == int(termino))
        stmt = stmt.where(or_(*condiciones))
    stmt = ordenar(stmt, orden_por, direccion, _ORDENABLES, por_defecto=Orden.fecha_creacion.desc())
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
    if not scope.ve_todo():
        if scope.cliente_id is None:
            raise HTTPException(
                status_code=400,
                detail="Tu usuario no esta vinculado a un cliente; contacta al administrador",
            )
        data["cliente_id"] = scope.cliente_id
    # El staff sí debe indicar el cliente (el campo es opcional solo para el rol Cliente).
    if data.get("cliente_id") is None:
        raise HTTPException(status_code=400, detail="Indica el cliente de la orden (cliente_id)")
    cliente = await db.get(Cliente, data["cliente_id"])
    if cliente is None or not cliente.activo:
        raise HTTPException(status_code=400, detail="cliente_id invalido o inactivo")

    data["lat_origen"], data["lon_origen"] = await resolver_coords(
        data.get("direccion_origen"), data.get("lat_origen"), data.get("lon_origen")
    )
    # Normaliza la lista de destinos (multidestino o uno legacy) y geocodifica cada uno.
    destinos = _normalizar_destinos(data)
    if not destinos or any(not d.get("direccion") for d in destinos):
        raise HTTPException(status_code=400, detail="Cada destino debe tener dirección")
    for d in destinos:
        d["lat"], d["lon"] = await resolver_coords(d.get("direccion"), d.get("lat"), d.get("lon"))
    # La orden conserva el primer destino en sus columnas legacy (compatibilidad/UI).
    principal = destinos[0]
    data["direccion_destino"] = principal["direccion"]
    data["distrito_destino"] = principal.get("distrito")
    data["lat_destino"], data["lon_destino"] = principal.get("lat"), principal.get("lon")

    # Precio calculado por el servidor: suma de tramos (uno por destino).
    cot = None
    try:
        cot = await _cotizar_destinos(db, data["lon_origen"], data["lat_origen"], destinos,
                                      data.get("nivel_servicio", "estandar"), data.get("programado_para"))
    except Exception as exc:  # noqa: BLE001 - OSRM puede fallar; no bloquea la creación
        import logging
        logging.getLogger(__name__).warning("No se pudo calcular precio de la orden: %s", exc)
    total = Decimal(str(cot["total"])) if cot else None
    data["total"] = total
    if scope.ve_todo() and ajuste_monto is not None:
        data["ajuste_monto"] = ajuste_monto
        data["ajuste_motivo"] = ajuste_motivo
        data["ajuste_por"] = scope.user.id
        if total is not None:
            data["total"] = max(Decimal("0"), total + Decimal(str(ajuste_monto)))

    # No se persisten en la fila de orden: la lista de destinos ni el paquete legacy top-level
    # (peso/dims ya viven en cada Destino; `_normalizar_destinos` ya los plegó arriba).
    data.pop("destinos", None)
    for _f in ("peso_kg", "largo_cm", "ancho_cm", "alto_cm"):
        data.pop(_f, None)

    es_cliente = not scope.ve_todo() and scope.cliente_id is not None
    estado_inicial = "Pendiente de Pago" if es_cliente else "Pendiente"
    orden = Orden(**data, estado=estado_inicial)
    db.add(orden)
    await db.flush()

    # Crea las filas de destino (con su subtotal de tramo).
    subtotales = [t["total"] for t in (cot["tramos"] if cot else [])]
    for i, d in enumerate(destinos):
        db.add(Destino(
            orden_id=orden.id, secuencia=i + 1,
            direccion=d["direccion"], distrito=d.get("distrito"),
            lat=d.get("lat"), lon=d.get("lon"),
            peso_kg=d.get("peso_kg"), largo_cm=d.get("largo_cm"),
            ancho_cm=d.get("ancho_cm"), alto_cm=d.get("alto_cm"),
            nombre_destinatario=d.get("nombre_destinatario"),
            subtotal=Decimal(str(subtotales[i])) if i < len(subtotales) else None,
        ))
    await db.commit()
    await db.refresh(orden)

    oid = orden.id
    await autogenerar_ruta(db, orden, mongo_db)
    if not es_cliente:
        await publish(
            CANAL_STAFF,
            {"tipo": "orden", "accion": "creada", "orden_id": oid, "cliente_id": orden.cliente_id, "estado": orden.estado},
        )
    return await _get_orden_full(db, oid)


@router.post("/cotizar", response_model=CotizacionResponse)
async def cotizar_orden_endpoint(
    payload: CotizarRequest,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("ordenes", "read")),
):
    """Cotización (precio calculado, suma de tramos) sin crear la orden, para mostrarla
    en vivo al cliente antes de pagar."""
    destinos = [dict(d) for d in payload.destinos] if payload.destinos else [{
        "lat": payload.lat_destino, "lon": payload.lon_destino,
        "peso_kg": payload.peso_kg, "largo_cm": payload.largo_cm,
        "ancho_cm": payload.ancho_cm, "alto_cm": payload.alto_cm,
    }]
    if not any(d.get("lon") is not None and d.get("lat") is not None for d in destinos):
        raise HTTPException(status_code=400, detail="Indica al menos un destino con coordenadas")
    try:
        return await cotizar_orden_precio(
            db, payload.lon_origen, payload.lat_origen,
            [d for d in destinos if d.get("lon") is not None and d.get("lat") is not None],
            nivel_servicio=payload.nivel_servicio, cuando=payload.programado_para,
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
    orden = await _get_orden_full(db, orden_id)
    if orden is None or not await orden_en_alcance(db, scope, orden):
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return orden


async def _cancelar_orden(db: AsyncSession, orden: Orden) -> None:
    """Cancela la orden LIBERANDO sus recursos (no hace commit; el llamador decide):
    los destinos pendientes quedan 'Fallida', y si la orden pertenecía a un run activo
    y ya no le queda trabajo, la asignación se cierra ('Cancelada') y el conductor
    vuelve a 'Disponible' — evita asignaciones fantasma y conductores 'Ocupado' eternos."""
    orden.estado = "Cancelado"
    destinos = (await db.execute(select(Destino).where(Destino.orden_id == orden.id))).scalars().all()
    for d in destinos:
        if d.estado == "Pendiente":
            d.estado = "Fallida"
            d.nota = "Orden cancelada"
    # Run activo que contiene esta orden (vía la tabla puente asignacion_ordenes).
    asignacion = (
        await db.execute(
            select(Asignacion)
            .join(asignacion_ordenes, asignacion_ordenes.c.asignacion_id == Asignacion.id)
            .where(
                asignacion_ordenes.c.orden_id == orden.id,
                Asignacion.estado.in_(("Asignada", "EnCurso")),
            )
            .order_by(Asignacion.id.desc())
        )
    ).scalars().first()
    if asignacion is None:
        return
    # ¿Le queda trabajo activo al run? (otras órdenes aún no terminales)
    activas = [o for o in asignacion.ordenes if o.id != orden.id and o.estado not in ("Entregado", "Cancelado")]
    if not activas:
        asignacion.estado = "Cancelada"
        asignacion.fecha_fin = datetime.now(timezone.utc)
        # Lock de fila del conductor (mismo criterio que create_asignacion).
        conductor = (
            await db.execute(
                select(Conductor).where(Conductor.id == asignacion.conductor_id).with_for_update()
            )
        ).scalar_one_or_none()
        if conductor is not None and conductor.disponibilidad == "Ocupado":
            conductor.disponibilidad = "Disponible"


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
    # Cambios de estado a mano: solo transiciones legales (core/estados.py). Los estados
    # de avance se alcanzan por sus endpoints (asignar/iniciar/entregar), no editando.
    nuevo_estado = update.pop("estado", None)
    estado_cambio = nuevo_estado is not None and nuevo_estado != orden.estado
    if estado_cambio:
        validar_transicion("orden", orden.estado, nuevo_estado, TRANSICIONES_ORDEN)
        if nuevo_estado == "Cancelado":
            # Cancelar libera conductor/asignación: misma rutina que DELETE /ordenes/{id}.
            await _cancelar_orden(db, orden)
        else:
            orden.estado = nuevo_estado
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

    # Recalcular el precio (suma de tramos sobre los destinos vigentes) si cambió algo
    # que lo afecta o si el staff aplica/ajusta el override.
    # El paquete ya no se edita a nivel de orden (se hace por destino y ese endpoint recotiza);
    # aquí solo disparan recálculo los cambios de origen/destino-legacy/nivel/programación.
    afecta_precio = any(
        c in update for c in (
            "lat_origen", "lon_origen", "lat_destino", "lon_destino",
            "nivel_servicio", "programado_para",
        )
    )
    if afecta_precio or (scope.ve_todo() and ajuste_monto is not None):
        destinos = (
            await db.execute(select(Destino).where(Destino.orden_id == orden.id).order_by(Destino.secuencia))
        ).scalars().all()
        destinos_data = [{
            "lat": d.lat, "lon": d.lon, "peso_kg": d.peso_kg, "largo_cm": d.largo_cm,
            "ancho_cm": d.ancho_cm, "alto_cm": d.alto_cm,
        } for d in destinos]
        try:
            cot = await _cotizar_destinos(db, orden.lon_origen, orden.lat_origen, destinos_data,
                                          orden.nivel_servicio, orden.programado_para)
            base = Decimal(str(cot["total"])) if cot else orden.total
        except Exception:  # noqa: BLE001
            base = orden.total
        if scope.ve_todo() and ajuste_monto is not None:
            orden.ajuste_monto = ajuste_monto
            orden.ajuste_motivo = ajuste_motivo
            orden.ajuste_por = scope.user.id
        ajuste = Decimal(str(orden.ajuste_monto)) if orden.ajuste_monto is not None else Decimal("0")
        orden.total = max(Decimal("0"), (base or Decimal("0")) + ajuste) if base is not None else None

    await db.commit()
    if estado_cambio:
        evento = {"tipo": "orden", "accion": "estado", "orden_id": orden.id, "estado": orden.estado}
        await publish(canal_cliente(orden.cliente_id), evento)
        await publish(CANAL_STAFF, evento)
    return await _get_orden_full(db, orden_id)


_ESTADOS_EDITABLES = ("Pendiente de Pago", "Pendiente")


async def _recalcular_total_y_ruta(db: AsyncSession, orden: Orden, mongo_db) -> None:
    """Recalcula el total (suma de tramos, preservando el ajuste) y regenera la ruta
    tras agregar/quitar destinos. Actualiza el subtotal de cada destino."""
    destinos = (
        await db.execute(select(Destino).where(Destino.orden_id == orden.id).order_by(Destino.secuencia))
    ).scalars().all()
    destinos_data = [{
        "lat": d.lat, "lon": d.lon, "peso_kg": d.peso_kg, "largo_cm": d.largo_cm,
        "ancho_cm": d.ancho_cm, "alto_cm": d.alto_cm,
    } for d in destinos]
    try:
        cot = await _cotizar_destinos(db, orden.lon_origen, orden.lat_origen, destinos_data,
                                      orden.nivel_servicio, orden.programado_para)
    except Exception:  # noqa: BLE001
        cot = None
    if cot:
        for d, tramo in zip(destinos, cot["tramos"]):
            d.subtotal = Decimal(str(tramo["total"]))
        ajuste = Decimal(str(orden.ajuste_monto)) if orden.ajuste_monto is not None else Decimal("0")
        orden.total = max(Decimal("0"), Decimal(str(cot["total"])) + ajuste)
    # La columna legacy refleja el primer destino.
    if destinos:
        orden.direccion_destino = destinos[0].direccion
        orden.lat_destino, orden.lon_destino = destinos[0].lat, destinos[0].lon
    await db.commit()
    await db.refresh(orden)
    try:
        await autogenerar_ruta(db, orden, mongo_db)
    except Exception:  # noqa: BLE001
        await db.rollback()


@router.post("/{orden_id}/destinos", response_model=OrdenResponse, status_code=status.HTTP_201_CREATED)
async def add_destino(
    orden_id: int,
    payload: DestinoIn,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("ordenes", "write")),
):
    """Agrega un destino a una orden aún editable; recalcula precio y ruta."""
    orden = await db.get(Orden, orden_id)
    if orden is None or not await orden_en_alcance(db, scope, orden):
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    if orden.estado not in _ESTADOS_EDITABLES:
        raise HTTPException(status_code=409, detail=f"No se pueden editar destinos con la orden en '{orden.estado}'")
    if not payload.direccion:
        raise HTTPException(status_code=400, detail="El destino requiere dirección")
    lat, lon = await resolver_coords(payload.direccion, payload.lat, payload.lon)
    maxseq = (await db.execute(select(func.max(Destino.secuencia)).where(Destino.orden_id == orden_id))).scalar() or 0
    db.add(Destino(
        orden_id=orden_id, secuencia=maxseq + 1,
        direccion=payload.direccion, distrito=payload.distrito, lat=lat, lon=lon,
        peso_kg=payload.peso_kg, largo_cm=payload.largo_cm, ancho_cm=payload.ancho_cm, alto_cm=payload.alto_cm,
        nombre_destinatario=payload.nombre_destinatario,
    ))
    await db.commit()
    await _recalcular_total_y_ruta(db, orden, mongo_db)
    return await _get_orden_full(db, orden_id)


@router.patch("/{orden_id}/destinos/{destino_id}", response_model=OrdenResponse)
async def update_destino(
    orden_id: int,
    destino_id: int,
    payload: DestinoUpdate,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("ordenes", "write")),
):
    """Edita un destino (dirección y/o peso/dimensiones) de una orden aún editable;
    recalcula precio y ruta (mismo criterio que agregar/quitar destinos)."""
    orden = await db.get(Orden, orden_id)
    if orden is None or not await orden_en_alcance(db, scope, orden):
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    if orden.estado not in _ESTADOS_EDITABLES:
        raise HTTPException(status_code=409, detail=f"No se pueden editar destinos con la orden en '{orden.estado}'")
    destino = await db.get(Destino, destino_id)
    if destino is None or destino.orden_id != orden_id:
        raise HTTPException(status_code=404, detail="Destino no encontrado")
    update = payload.model_dump(exclude_unset=True)
    if "direccion" in update and not update["direccion"]:
        raise HTTPException(status_code=400, detail="El destino requiere dirección")
    # Si cambia la dirección sin coordenadas explícitas, re-geocodificar.
    if "direccion" in update and update.get("lat") is None and update.get("lon") is None:
        update["lat"], update["lon"] = await resolver_coords(update["direccion"], None, None)
    for k, v in update.items():
        setattr(destino, k, v)
    await db.commit()
    await _recalcular_total_y_ruta(db, orden, mongo_db)
    return await _get_orden_full(db, orden_id)


@router.delete("/{orden_id}/destinos/{destino_id}", response_model=OrdenResponse)
async def delete_destino(
    orden_id: int,
    destino_id: int,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("ordenes", "write")),
):
    """Quita un destino de una orden aún editable; recalcula precio y ruta."""
    orden = await db.get(Orden, orden_id)
    if orden is None or not await orden_en_alcance(db, scope, orden):
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    if orden.estado not in _ESTADOS_EDITABLES:
        raise HTTPException(status_code=409, detail=f"No se pueden editar destinos con la orden en '{orden.estado}'")
    destino = await db.get(Destino, destino_id)
    if destino is None or destino.orden_id != orden_id:
        raise HTTPException(status_code=404, detail="Destino no encontrado")
    restantes = (await db.execute(select(func.count(Destino.id)).where(Destino.orden_id == orden_id))).scalar_one()
    if restantes <= 1:
        raise HTTPException(status_code=400, detail="La orden debe tener al menos un destino")
    await db.delete(destino)
    await db.commit()
    await _recalcular_total_y_ruta(db, orden, mongo_db)
    return await _get_orden_full(db, orden_id)


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
    # Misma regla que el PATCH: solo se cancela desde estados no terminales.
    validar_transicion("orden", orden.estado, "Cancelado", TRANSICIONES_ORDEN)
    # Cancela liberando conductor/asignación (evita estados fantasma).
    await _cancelar_orden(db, orden)
    await db.commit()
    # Notifica el cambio de estado al dueño de la orden y a la operación.
    evento = {"tipo": "orden", "accion": "estado", "orden_id": orden.id, "estado": "Cancelado"}
    await publish(canal_cliente(orden.cliente_id), evento)
    await publish(CANAL_STAFF, evento)
