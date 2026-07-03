from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from api.dependencies import UserScope, get_mongo_db, get_scope, orden_en_alcance, require_permiso
from core.database import get_db
from core.realtime import CANAL_STAFF, canal_cliente, publish
from models.asignaciones import Asignacion
from models.conductores import Conductor
from models.ordenes import Orden
from models.rutas import RutaPlanificada
from schemas.mongo_tracking import GeocercaIn, GeocercaOut, GeocercaUpdate, GPSPingIn, GPSPingOut
from schemas.seguimiento import (
    AsignacionSeguimiento,
    OrdenSeguimientoResponse,
    ParadaSeguimiento,
    PosicionActual,
    PuntoGeo,
    RutaSeguimiento,
)
from services import incidencias_service
from services.mongo import entregas_service, geocerca_service, tracking_service

router = APIRouter(tags=["tracking"])


def _to_float(value) -> Optional[float]:
    return float(value) if value is not None else None


@router.post("/tracking/ping", response_model=GPSPingOut, status_code=status.HTTP_201_CREATED)
async def post_ping(
    payload: GPSPingIn,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("tracking", "write")),
):
    asignacion = await db.get(Asignacion, payload.asignacion_id)
    if asignacion is None:
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    # El conductor solo emite GPS de SU asignación y mientras esté EnCurso; se fuerzan
    # conductor/vehículo desde la asignación (no se confía en el payload del cliente).
    if not scope.ve_todo():
        if scope.conductor_id is None or asignacion.conductor_id != scope.conductor_id:
            raise HTTPException(status_code=404, detail="Asignacion no encontrada")
        if asignacion.estado != "EnCurso":
            raise HTTPException(status_code=400, detail="La asignación no está en curso")
        payload.conductor_id = asignacion.conductor_id
        if asignacion.vehiculo_placa:
            payload.vehiculo_placa = asignacion.vehiculo_placa

    doc = await tracking_service.crear_ping(mongo_db, payload)

    # Empuja la nueva posición al cliente dueño de la orden (seguimiento en vivo).
    orden = await db.get(Orden, asignacion.orden_id)
    if orden is not None:
        await publish(canal_cliente(orden.cliente_id), {"tipo": "orden", "accion": "posicion", "orden_id": orden.id})

    # Detección de desvío: si el punto cae fuera del corredor activo de la orden, se crea
    # una incidencia automática (anti-spam) y se alerta a la operación en vivo.
    if asignacion.estado == "EnCurso" and orden is not None:
        try:
            fuera = await geocerca_service.punto_fuera_de_corredor(
                mongo_db, orden.id, payload.lon, payload.lat
            )
            if fuera:
                inc = await incidencias_service.crear_incidencia_desvio(db, asignacion.id)
                if inc is not None:
                    await publish(CANAL_STAFF, {
                        "tipo": "incidencia", "accion": "desvio",
                        "incidencia_id": inc.id, "asignacion_id": asignacion.id,
                        "orden_id": orden.id, "severidad": inc.severidad,
                    })
        except Exception as exc:  # noqa: BLE001 - la detección nunca debe romper el ping
            import logging
            logging.getLogger(__name__).warning("Fallo detección de desvío: %s", exc)
    return doc


@router.get("/tracking/asignacion/{asignacion_id}", response_model=list[GPSPingOut])
async def get_tracking_asignacion(
    asignacion_id: int,
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    limit: int = Query(500, le=2000),
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("tracking", "read")),
):
    return await tracking_service.listar_por_asignacion(mongo_db, asignacion_id, desde, hasta, limit)


@router.get("/tracking/asignacion/{asignacion_id}/ultimo", response_model=GPSPingOut)
async def get_ultimo_ping(
    asignacion_id: int,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("tracking", "read")),
):
    doc = await tracking_service.ultimo_ping(mongo_db, asignacion_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Sin pings para esta asignacion")
    return doc


@router.get("/tracking/asignacion/{asignacion_id}/estadisticas")
async def estadisticas_asignacion(
    asignacion_id: int,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("tracking", "read")),
):
    """Distancia total recorrida, duracion y velocidad promedio segun pings GPS."""
    return await tracking_service.estadisticas_asignacion(mongo_db, asignacion_id)


@router.get("/tracking/flota")
async def flota_activa(
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("tracking", "read")),
):
    """Mapa operativo de la flota en UNA llamada: cada run EnCurso con su conductor,
    vehículo, última posición GPS conocida (sin ventana temporal: no 'desaparece')
    y la geometría de la ruta vigente para dibujarla."""
    asignaciones = (
        await db.execute(
            select(Asignacion).where(Asignacion.estado == "EnCurso").order_by(Asignacion.id.desc())
        )
    ).scalars().all()
    flota = []
    for a in asignaciones:
        conductor = await db.get(Conductor, a.conductor_id)
        ultimo = await tracking_service.ultimo_ping(mongo_db, a.id)
        posicion = None
        if ultimo is not None:
            coords = ultimo["location"]["coordinates"]
            posicion = {
                "lon": coords[0],
                "lat": coords[1],
                "speed_kmh": ultimo.get("speed_kmh"),
                "timestamp": ultimo["timestamp"],
            }
        ruta = (
            await db.execute(
                select(RutaPlanificada)
                .where(RutaPlanificada.orden_id == a.orden_id)
                .order_by(RutaPlanificada.id.desc())
            )
        ).scalars().first()
        flota.append({
            "asignacion_id": a.id,
            "orden_id": a.orden_id,
            "orden_ids": [o.id for o in a.ordenes],
            "conductor_id": a.conductor_id,
            "conductor_nombre": conductor.nombre if conductor else None,
            "vehiculo_placa": a.vehiculo_placa,
            "fecha_inicio": a.fecha_inicio,
            "posicion": posicion,
            "ruta_geometria": ruta.geometria if ruta is not None else None,
        })
    return flota


@router.get("/tracking/conductores-cerca")
async def conductores_cerca_de_punto(
    lon: float = Query(..., ge=-180, le=180),
    lat: float = Query(..., ge=-90, le=90),
    radio_m: int = Query(2000, ge=10, le=50000),
    ventana_min: int = Query(5, ge=1, le=60),
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("tracking", "read")),
):
    """Conductores con ping reciente dentro del radio. Usa $geoNear sobre gps_tracking."""
    return await tracking_service.conductores_cerca(mongo_db, lon, lat, radio_m, ventana_min)


@router.get("/tracking/orden/{orden_id}", response_model=OrdenSeguimientoResponse)
async def seguimiento_orden(
    orden_id: int,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("tracking", "read")),
):
    """Vista agregada para la pantalla de trackeo: orden, asignacion activa, ultima
    posicion GPS, ruta, progreso de paradas y geocercas activas."""
    orden = await db.get(Orden, orden_id)
    # Solo el dueño (cliente), el conductor asignado o el staff pueden seguir la orden.
    if orden is None or not await orden_en_alcance(db, scope, orden):
        raise HTTPException(status_code=404, detail="Orden no encontrada")

    # Asignacion activa: preferir la EnCurso, si no la mas reciente.
    result = await db.execute(
        select(Asignacion).where(Asignacion.orden_id == orden_id).order_by(Asignacion.id.desc())
    )
    asignaciones = result.scalars().all()
    asignacion = next(
        (a for a in asignaciones if a.estado == "EnCurso"),
        asignaciones[0] if asignaciones else None,
    )

    asignacion_out = None
    posicion = None
    estadisticas = None
    entregas_out: list = []
    if asignacion is not None:
        conductor = await db.get(Conductor, asignacion.conductor_id)
        asignacion_out = AsignacionSeguimiento(
            id=asignacion.id,
            estado=asignacion.estado,
            conductor_id=asignacion.conductor_id,
            conductor_nombre=conductor.nombre if conductor else None,
            vehiculo_placa=asignacion.vehiculo_placa,
            fecha_inicio=asignacion.fecha_inicio,
            fecha_fin=asignacion.fecha_fin,
        )
        ultimo = await tracking_service.ultimo_ping(mongo_db, asignacion.id)
        if ultimo is not None:
            coords = ultimo["location"]["coordinates"]
            posicion = PosicionActual(
                lon=coords[0],
                lat=coords[1],
                speed_kmh=ultimo.get("speed_kmh"),
                heading=ultimo.get("heading"),
                timestamp=ultimo["timestamp"],
            )
        estadisticas = await tracking_service.estadisticas_asignacion(mongo_db, asignacion.id)
        entregas_out = await entregas_service.listar_por_asignacion(mongo_db, asignacion.id)

    # Ruta mas reciente de la orden + sus paradas + geocercas activas.
    result = await db.execute(
        select(RutaPlanificada)
        .options(selectinload(RutaPlanificada.paradas))
        .where(RutaPlanificada.orden_id == orden_id)
        .order_by(RutaPlanificada.id.desc())
    )
    ruta = result.scalars().first()
    ruta_out = None
    paradas_out: list[ParadaSeguimiento] = []
    geocercas: list = []
    if ruta is not None:
        ruta_out = RutaSeguimiento(
            id=ruta.id,
            distancia_km=_to_float(ruta.distancia_km),
            tiempo_estimado_segundos=ruta.tiempo_estimado.total_seconds() if ruta.tiempo_estimado is not None else None,
            geometria=ruta.geometria,
        )
        paradas_out = [
            ParadaSeguimiento(
                id=p.id,
                secuencia=p.secuencia,
                direccion=p.direccion,
                lat=_to_float(p.lat),
                lon=_to_float(p.lon),
                estado=p.estado,
                fecha_paso=p.fecha_paso,
                orden_id=p.orden_id,
                destino_id=p.destino_id,
            )
            for p in ruta.paradas
        ]
        geocercas = await geocerca_service.listar(mongo_db, ruta_id=ruta.id, activa=True)

    return OrdenSeguimientoResponse(
        orden_id=orden.id,
        estado=orden.estado,
        cliente_id=orden.cliente_id,
        origen=PuntoGeo(
            direccion=orden.direccion_origen,
            distrito=orden.distrito_origen,
            lat=_to_float(orden.lat_origen),
            lon=_to_float(orden.lon_origen),
        ),
        destino=PuntoGeo(
            direccion=orden.direccion_destino,
            distrito=orden.distrito_destino,
            lat=_to_float(orden.lat_destino),
            lon=_to_float(orden.lon_destino),
        ),
        asignacion=asignacion_out,
        posicion_actual=posicion,
        ruta=ruta_out,
        paradas=paradas_out,
        geocercas=geocercas,
        estadisticas=estadisticas,
        entregas=entregas_out,
    )


@router.get("/tracking/orden/{orden_id}/evidencia/{file_id}")
async def descargar_evidencia_seguimiento(
    orden_id: int,
    file_id: str,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("tracking", "read")),
):
    """Descarga una foto de prueba de entrega, accesible para el dueño de la orden
    (cliente), el conductor asignado o el staff (mismo alcance que el seguimiento)."""
    from fastapi.responses import StreamingResponse

    orden = await db.get(Orden, orden_id)
    if orden is None or not await orden_en_alcance(db, scope, orden):
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    grid_out = await entregas_service.abrir_descarga(mongo_db, file_id)
    if grid_out is None:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    metadata = grid_out.metadata or {}

    async def _iter():
        async for chunk in grid_out:
            yield chunk

    return StreamingResponse(
        _iter(),
        media_type=metadata.get("content_type") or "application/octet-stream",
        headers={"Content-Length": str(grid_out.length), "Content-Disposition": f'inline; filename="{grid_out.filename}"'},
    )


@router.post("/geocercas", response_model=GeocercaOut, status_code=status.HTTP_201_CREATED)
async def create_geocerca(
    payload: GeocercaIn,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("geocercas", "write")),
):
    return await geocerca_service.crear(mongo_db, payload)


@router.get("/geocercas", response_model=list[GeocercaOut])
async def list_geocercas(
    ruta_id: Optional[int] = None,
    activa: Optional[bool] = None,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("geocercas", "read")),
):
    return await geocerca_service.listar(mongo_db, ruta_id, activa)


@router.get("/geocercas/contiene", response_model=list[GeocercaOut])
async def geocercas_contienen_punto(
    lon: float = Query(..., ge=-180, le=180),
    lat: float = Query(..., ge=-90, le=90),
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("geocercas", "read")),
):
    return await geocerca_service.contiene_punto(mongo_db, lon, lat)


@router.get("/geocercas/{geocerca_id}", response_model=GeocercaOut)
async def get_geocerca(
    geocerca_id: str,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("geocercas", "read")),
):
    doc = await geocerca_service.obtener(mongo_db, geocerca_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Geocerca no encontrada")
    return doc


@router.patch("/geocercas/{geocerca_id}", response_model=GeocercaOut)
async def update_geocerca(
    geocerca_id: str,
    payload: GeocercaUpdate,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("geocercas", "write")),
):
    doc = await geocerca_service.actualizar(mongo_db, geocerca_id, payload.model_dump(exclude_unset=True))
    if doc is None:
        raise HTTPException(status_code=404, detail="Geocerca no encontrada")
    return doc


@router.delete("/geocercas/{geocerca_id}", status_code=status.HTTP_204_NO_CONTENT)
async def desactivar_geocerca(
    geocerca_id: str,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("geocercas", "delete")),
):
    ok = await geocerca_service.desactivar(mongo_db, geocerca_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Geocerca no encontrada")
