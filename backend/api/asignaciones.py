from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.dependencies import (
    UserScope,
    get_current_user,
    get_mongo_db,
    get_scope,
    require_permiso,
)
from core.database import get_db
from core.realtime import CANAL_STAFF, canal_cliente, publish
from sqlalchemy.orm import selectinload

from models.asignaciones import Asignacion
from models.calificaciones import Calificacion
from models.conductores import Conductor
from models.destinos import Destino
from models.incidencias import Incidencia
from models.ordenes import Orden
from models.rutas import Parada
from models.usuarios import Usuario
from models.vehiculos import Vehiculo
from schemas.asignaciones import (
    AsignacionCreate,
    AsignacionResponse,
    AsignacionUpdate,
    EntregaOut,
    FallarDestinoRequest,
    FinalizarAsignacionRequest,
    SugerenciaConductor,
)
from schemas.common import TipoEvidencia
from services.mongo import entregas_service, geocerca_service, tracking_service
from services.mongo.tracking_service import _haversine_m
from services import plaqueo_service, route_planner
from services.pricing_service import obtener_tarifa, peso_cobrable
from services.route_planner import generar_run

router = APIRouter(prefix="/asignaciones", tags=["asignaciones"])


def _solo_staff(scope: UserScope) -> None:
    if not scope.ve_todo():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acción reservada al personal interno")


def _asg_en_alcance(scope: UserScope, asignacion: Asignacion) -> bool:
    """El conductor solo opera SUS asignaciones; el staff todas."""
    if scope.ve_todo():
        return True
    if scope.conductor_id is not None:
        return asignacion.conductor_id == scope.conductor_id
    return False


async def _avisar_estado_orden(db: AsyncSession, orden: Orden | None) -> None:
    """Publica el cambio de estado de la orden a su cliente y a la operación."""
    if orden is None:
        return
    evento = {"tipo": "orden", "accion": "estado", "orden_id": orden.id, "estado": orden.estado}
    await publish(canal_cliente(orden.cliente_id), evento)
    await publish(CANAL_STAFF, evento)


@router.get("/", response_model=list[AsignacionResponse])
async def list_asignaciones(
    skip: int = 0,
    limit: int = Query(50, le=200),
    estado: str | None = None,
    conductor_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "read")),
):
    stmt = select(Asignacion)
    if not scope.ve_todo():
        # El conductor solo ve sus asignaciones; otros usuarios finales, ninguna.
        if scope.conductor_id is None:
            return []
        stmt = stmt.where(Asignacion.conductor_id == scope.conductor_id)
    elif conductor_id is not None:
        stmt = stmt.where(Asignacion.conductor_id == conductor_id)
    if estado is not None:
        stmt = stmt.where(Asignacion.estado == estado)
    stmt = stmt.order_by(Asignacion.id.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


async def _asg_full(db: AsyncSession, asignacion_id: int) -> Asignacion | None:
    return (
        await db.execute(
            select(Asignacion).options(selectinload(Asignacion.ordenes)).where(Asignacion.id == asignacion_id)
        )
    ).scalar_one_or_none()


@router.post("/", response_model=AsignacionResponse, status_code=status.HTTP_201_CREATED)
async def create_asignacion(
    payload: AsignacionCreate,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    _solo_staff(scope)
    # Una o varias órdenes agrupadas en la misma ruta del conductor (la 1ª es la principal).
    ids: list[int] = list(dict.fromkeys(payload.orden_ids or ([payload.orden_id] if payload.orden_id else [])))
    if not ids:
        raise HTTPException(status_code=400, detail="Indica una o varias órdenes")

    ordenes: list[Orden] = []
    for oid in ids:
        orden = await db.get(Orden, oid)
        if orden is None:
            raise HTTPException(status_code=404, detail=f"Orden {oid} no encontrada")
        if orden.estado != "Pendiente":
            raise HTTPException(status_code=400, detail=f"Orden {oid} no está Pendiente (actual: {orden.estado})")
        ordenes.append(orden)

    conductor = await db.get(Conductor, payload.conductor_id)
    if conductor is None or not conductor.activo:
        raise HTTPException(status_code=400, detail="Conductor invalido o inactivo")
    if conductor.disponibilidad != "Disponible":
        raise HTTPException(status_code=400, detail=f"Conductor no disponible (actual: {conductor.disponibilidad})")

    vehiculo = await db.get(Vehiculo, payload.vehiculo_placa)
    if vehiculo is None or not vehiculo.activo:
        raise HTTPException(status_code=400, detail="Vehiculo invalido o inactivo")
    if vehiculo.estado != "Operativo":
        raise HTTPException(status_code=400, detail=f"Vehiculo no operativo (actual: {vehiculo.estado})")

    # Plaqueo (centro histórico de Arequipa). Si un recojo/entrega cae DENTRO de la zona en
    # un día restringido, es inevitable y se bloquea; si solo la ruta cruza la zona pero los
    # puntos están fuera, se permite y la ruta se reconstruye rebordeando el centro.
    plaqueo = await plaqueo_service.evaluar_asignacion(db, mongo_db, ordenes, payload.vehiculo_placa)
    if plaqueo["bloquear"]:
        b = plaqueo["bloquear"]
        raise HTTPException(
            status_code=409,
            detail=(
                f"Plaqueo: el vehículo {b['placa']} (placa termina en {b['digito']}) no puede "
                f"circular el {b['dia']} y la orden {b['orden_id']} recoge/entrega dentro del centro "
                "histórico. Elige otro vehículo o reprograma la entrega."
            ),
        )
    evitar_zonas = plaqueo["reroute"]

    primary = ordenes[0]
    # Si el plaqueo obliga a rebordear pero no existe una ruta que evite el centro, se
    # bloquea (no se asigna un vehículo a una ruta que cruzaría ilegalmente la zona).
    if evitar_zonas and not await route_planner.run_es_evitable(db, primary, ordenes, mongo_db):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Plaqueo: con el vehículo {payload.vehiculo_placa} no se pudo trazar una ruta que "
                "evite el centro histórico ese día. Elige otro vehículo o reprograma la entrega."
            ),
        )
    asignacion = Asignacion(
        orden_id=primary.id, conductor_id=payload.conductor_id,
        vehiculo_placa=payload.vehiculo_placa, estado="Asignada",
    )
    asignacion.ordenes = ordenes
    db.add(asignacion)
    for orden in ordenes:
        orden.estado = "En Proceso"
    conductor.disponibilidad = "Ocupado"
    await db.commit()

    # Construye una única ruta consolidada (recojos + entregas) optimizada; rebordea la
    # zona de restricción si el plaqueo lo requiere.
    try:
        await generar_run(db, primary, ordenes, mongo_db=mongo_db, evitar_zonas=evitar_zonas)
    except Exception as exc:  # noqa: BLE001 - la ruta es best-effort
        import logging
        logging.getLogger(__name__).warning("No se pudo generar la ruta del run %s: %s", asignacion.id, exc)
        await db.rollback()
    return await _asg_full(db, asignacion.id)


@router.get("/sugerencia", response_model=list[SugerenciaConductor])
async def sugerir_conductor(
    orden_id: int | None = None,
    orden_ids: list[int] | None = Query(None),
    limit: int = Query(5, le=20),
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "read")),
):
    """Sugiere los mejores conductores para una o varias órdenes a agrupar: disponibles,
    con vehículo operativo y CAPACIDAD suficiente, ordenados por capacidad suficiente,
    cercanía al origen (última posición GPS) y rating."""
    _solo_staff(scope)
    ids = list(dict.fromkeys(orden_ids or ([orden_id] if orden_id else [])))
    if not ids:
        raise HTTPException(status_code=400, detail="Indica una o varias órdenes")
    ordenes = []
    for oid in ids:
        o = await db.get(Orden, oid)
        if o is None:
            raise HTTPException(status_code=404, detail=f"Orden {oid} no encontrada")
        ordenes.append(o)

    # Peso requerido = suma del peso cobrable de todos los destinos de todas las órdenes.
    tarifa = await obtener_tarifa(db)
    destinos = (
        await db.execute(select(Destino).where(Destino.orden_id.in_(ids)))
    ).scalars().all()
    peso_total = float(sum(
        peso_cobrable(tarifa, float(d.peso_kg) if d.peso_kg else None,
                      float(d.largo_cm) if d.largo_cm else None,
                      float(d.ancho_cm) if d.ancho_cm else None,
                      float(d.alto_cm) if d.alto_cm else None)
        for d in destinos
    ))
    peso_total = round(peso_total, 2)

    rows = (
        await db.execute(
            select(Conductor, Vehiculo)
            .join(Vehiculo, Conductor.vehiculo_placa == Vehiculo.placa)
            .where(
                Conductor.activo.is_(True),
                Conductor.disponibilidad == "Disponible",
                Vehiculo.activo.is_(True),
                Vehiculo.estado == "Operativo",
            )
        )
    ).all()

    primary = ordenes[0]
    lon_o = float(primary.lon_origen) if primary.lon_origen is not None else None
    lat_o = float(primary.lat_origen) if primary.lat_origen is not None else None

    # Fechas de entrega cuya ruta cruza la zona de restricción (para evaluar plaqueo por placa).
    fechas_cruce = await plaqueo_service.fechas_con_cruce(db, mongo_db, ordenes)

    sugerencias: list[SugerenciaConductor] = []
    for cond, veh in rows:
        dist_km = None
        if lon_o is not None and lat_o is not None:
            pos = await tracking_service.ultima_posicion_conductor(mongo_db, cond.id)
            if pos:
                c = pos["location"]["coordinates"]
                dist_km = round(_haversine_m(c[0], c[1], lon_o, lat_o) / 1000.0, 2)
        prom, total = (
            await db.execute(
                select(func.avg(Calificacion.puntaje), func.count(Calificacion.id)).where(
                    Calificacion.conductor_id == cond.id
                )
            )
        ).one()
        cap = float(veh.capacidad_kg) if veh.capacidad_kg is not None else None
        suficiente = cap is None or peso_total == 0 or cap >= peso_total
        restringido = any(plaqueo_service.placa_restringida(cond.vehiculo_placa, f) for f in fechas_cruce)
        sugerencias.append(
            SugerenciaConductor(
                conductor_id=cond.id,
                nombre=cond.nombre,
                vehiculo_placa=cond.vehiculo_placa,
                distancia_km=dist_km,
                rating=round(float(prom), 2) if prom is not None else None,
                total_calificaciones=total or 0,
                capacidad_kg=cap,
                peso_requerido_kg=peso_total,
                suficiente=suficiente,
                restringido_plaqueo=restringido,
            )
        )

    # No restringidos y con capacidad primero; luego más cercano; sin posición al final; mejor rating.
    sugerencias.sort(key=lambda s: (s.restringido_plaqueo, not s.suficiente, s.distancia_km is None, s.distancia_km or 0.0, -(s.rating or 0.0)))
    return sugerencias[:limit]


@router.get("/{asignacion_id}", response_model=AsignacionResponse)
async def get_asignacion(
    asignacion_id: int,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "read")),
):
    asignacion = await _asg_full(db, asignacion_id)
    if asignacion is None or not _asg_en_alcance(scope, asignacion):
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    return asignacion


@router.patch("/{asignacion_id}", response_model=AsignacionResponse)
async def update_asignacion(
    asignacion_id: int,
    payload: AsignacionUpdate,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    _solo_staff(scope)
    asignacion = await db.get(Asignacion, asignacion_id)
    if asignacion is None:
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(asignacion, k, v)
    await db.commit()
    await db.refresh(asignacion)
    return asignacion


@router.patch("/{asignacion_id}/iniciar", response_model=AsignacionResponse)
async def iniciar_asignacion(
    asignacion_id: int,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    asignacion = await _asg_full(db, asignacion_id)
    if asignacion is None or not _asg_en_alcance(scope, asignacion):
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    if asignacion.estado != "Asignada":
        raise HTTPException(status_code=400, detail=f"Asignacion no esta Asignada (actual: {asignacion.estado})")
    asignacion.estado = "EnCurso"
    asignacion.fecha_inicio = datetime.now(timezone.utc)
    # Todas las órdenes del run pasan a 'En Tránsito'.
    for orden in asignacion.ordenes:
        orden.estado = "En Tránsito"
    await db.commit()
    for orden in asignacion.ordenes:
        await _avisar_estado_orden(db, orden)
    return await _asg_full(db, asignacion_id)


async def _cerrar_completados(db: AsyncSession, asignacion: Asignacion, ahora) -> list[Orden]:
    """Cierra las órdenes cuyos destinos están todos en estado terminal (Entregado o
    Fallida): la orden queda 'Entregado' si al menos uno se entregó, o 'Cancelado' si
    ninguno. Si todo el run terminó, finaliza la asignación y libera al conductor.
    Devuelve las órdenes cuyo estado cambió (para avisar tras el commit)."""
    cambiadas: list[Orden] = []
    todos_terminales = True
    for orden in asignacion.ordenes:
        ds = (await db.execute(select(Destino).where(Destino.orden_id == orden.id))).scalars().all()
        terminales = [d for d in ds if d.estado in ("Entregado", "Fallida")]
        if len(terminales) < len(ds):
            todos_terminales = False
            continue
        if orden.estado in ("Entregado", "Cancelado"):
            continue
        orden.estado = "Entregado" if any(d.estado == "Entregado" for d in ds) else "Cancelado"
        cambiadas.append(orden)
    if todos_terminales and asignacion.estado == "EnCurso":
        asignacion.estado = "Finalizada"
        asignacion.fecha_fin = ahora
        conductor = await db.get(Conductor, asignacion.conductor_id)
        if conductor is not None:
            conductor.disponibilidad = "Disponible"
    return cambiadas


@router.patch("/{asignacion_id}/finalizar", response_model=AsignacionResponse)
async def finalizar_asignacion(
    asignacion_id: int,
    payload: FinalizarAsignacionRequest | None = None,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    """Cierre forzado por el staff (excepción): finaliza el run sin foto del conductor,
    exigiendo un motivo que queda registrado como incidencia para auditoría."""
    _solo_staff(scope)
    asignacion = await _asg_full(db, asignacion_id)
    if asignacion is None:
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    if asignacion.estado != "EnCurso":
        raise HTTPException(status_code=400, detail=f"Asignacion no esta EnCurso (actual: {asignacion.estado})")
    motivo = (payload.nota if payload else None) or ""
    if not motivo.strip():
        raise HTTPException(status_code=400, detail="Indica el motivo del cierre forzado")

    ahora = datetime.now(timezone.utc)
    receptor = (payload.receptor if payload else None) or "Cierre forzado"
    destinos = (
        await db.execute(select(Destino).where(Destino.orden_id.in_([o.id for o in asignacion.ordenes])))
    ).scalars().all()
    for d in destinos:
        if d.estado not in ("Entregado", "Fallida"):
            d.estado = "Entregado"
            d.entrega_receptor = receptor
            d.fecha_entrega = ahora
            d.nota = f"Cierre forzado: {motivo}"
            if payload and payload.lat is not None:
                d.entrega_lat = payload.lat
            if payload and payload.lon is not None:
                d.entrega_lon = payload.lon
            # Sincroniza la parada de la ruta planificada (igual que entregar/fallar destino).
            await _marcar_parada(db, d.id, ahora, "Visitada")
    asignacion.entrega_receptor = receptor
    # Registro de auditoría: incidencia del cierre forzado.
    db.add(Incidencia(asignacion_id=asignacion_id, tipo="Cierre forzado", severidad=2,
                      origen="admin", notas=motivo))
    cambiadas = await _cerrar_completados(db, asignacion, ahora)
    await db.commit()
    for orden in cambiadas:
        await _avisar_estado_orden(db, orden)
    return await _asg_full(db, asignacion_id)


@router.patch("/{asignacion_id}/reabrir", response_model=AsignacionResponse)
async def reabrir_asignacion(
    asignacion_id: int,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    """Reapertura liviana de un run cerrado por error: vuelve la asignación a 'EnCurso',
    sus órdenes a 'En Tránsito' y ocupa de nuevo al conductor. Conserva los destinos,
    paradas y la evidencia ya registrados (no borra el trabajo hecho)."""
    _solo_staff(scope)
    asignacion = await _asg_full(db, asignacion_id)
    if asignacion is None:
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    if asignacion.estado != "Finalizada":
        raise HTTPException(status_code=400, detail=f"Solo se reabre una asignacion Finalizada (actual: {asignacion.estado})")

    asignacion.estado = "EnCurso"
    asignacion.fecha_fin = None
    cambiadas: list[Orden] = []
    for orden in asignacion.ordenes:
        if orden.estado in ("Entregado", "Cancelado"):
            orden.estado = "En Tránsito"
            cambiadas.append(orden)
    conductor = await db.get(Conductor, asignacion.conductor_id)
    if conductor is not None:
        conductor.disponibilidad = "Ocupado"
    await db.commit()
    for orden in cambiadas:
        await _avisar_estado_orden(db, orden)
    return await _asg_full(db, asignacion_id)


async def _validar_destino_en_curso(db, asignacion_id, destino_id, scope):
    asignacion = await _asg_full(db, asignacion_id)
    if asignacion is None or not _asg_en_alcance(scope, asignacion):
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    if asignacion.estado != "EnCurso":
        raise HTTPException(status_code=400, detail=f"Asignacion no esta EnCurso (actual: {asignacion.estado})")
    destino = await db.get(Destino, destino_id)
    if destino is None or destino.orden_id not in {o.id for o in asignacion.ordenes}:
        raise HTTPException(status_code=404, detail="Destino no pertenece a esta asignación")
    if destino.estado in ("Entregado", "Fallida"):
        raise HTTPException(status_code=400, detail=f"El destino ya está {destino.estado}")
    return asignacion, destino


async def _marcar_parada(db, destino_id, ahora, estado="Visitada"):
    parada = (await db.execute(select(Parada).where(Parada.destino_id == destino_id))).scalars().first()
    if parada is not None:
        parada.estado = estado
        parada.fecha_paso = ahora


@router.post("/{asignacion_id}/destinos/{destino_id}/entregar", response_model=EntregaOut, status_code=status.HTTP_201_CREATED)
async def entregar_destino(
    asignacion_id: int,
    destino_id: int,
    receptor: str = Form(...),
    lat: float | None = Form(None),
    lon: float | None = Form(None),
    archivos: list[UploadFile] = File(..., description="Foto/firma de la entrega de este destino"),
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    current_user: Usuario = Depends(get_current_user),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    """Entrega UN destino del run con evidencia obligatoria. Al quedar todos los destinos
    de una orden en estado terminal, la orden se cierra; al terminar el run, la asignación
    queda 'Finalizada'."""
    asignacion, destino = await _validar_destino_en_curso(db, asignacion_id, destino_id, scope)
    entrega = await entregas_service.crear_con_archivos(
        mongo_db, asignacion_id=asignacion_id, archivos=archivos, tipo="foto",
        descripcion=f"Entrega destino #{destino_id}", lat=lat, lon=lon, receptor=receptor,
        uploaded_by=current_user.id, destino_id=destino_id,
    )
    ahora = datetime.now(timezone.utc)
    destino.estado = "Entregado"
    destino.entrega_receptor = receptor
    destino.entrega_lat, destino.entrega_lon = lat, lon
    destino.fecha_entrega = ahora
    await _marcar_parada(db, destino_id, ahora, "Visitada")
    cambiadas = await _cerrar_completados(db, asignacion, ahora)
    await db.commit()
    for orden in cambiadas:
        await _avisar_estado_orden(db, orden)
    return entrega


@router.post("/{asignacion_id}/destinos/{destino_id}/fallar", response_model=AsignacionResponse)
async def fallar_destino(
    asignacion_id: int,
    destino_id: int,
    payload: FallarDestinoRequest,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    """Marca un destino como NO entregado (cliente ausente, dirección incorrecta…) con
    motivo. Crea una incidencia y cierra la orden/run cuando ya no quedan destinos pendientes."""
    if not payload.motivo.strip():
        raise HTTPException(status_code=400, detail="Indica el motivo de la no entrega")
    asignacion, destino = await _validar_destino_en_curso(db, asignacion_id, destino_id, scope)
    ahora = datetime.now(timezone.utc)
    destino.estado = "Fallida"
    destino.nota = payload.motivo.strip()
    destino.fecha_entrega = ahora
    await _marcar_parada(db, destino_id, ahora, "Omitida")
    db.add(Incidencia(asignacion_id=asignacion_id, tipo="Entrega fallida", severidad=3,
                      origen="chofer", notas=payload.motivo.strip()))
    cambiadas = await _cerrar_completados(db, asignacion, ahora)
    await db.commit()
    for orden in cambiadas:
        await _avisar_estado_orden(db, orden)
    return await _asg_full(db, asignacion_id)


@router.post(
    "/{asignacion_id}/prueba-entrega",
    response_model=EntregaOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_prueba_entrega(
    asignacion_id: int,
    tipo: TipoEvidencia = Form("foto"),
    descripcion: str | None = Form(None),
    receptor: str | None = Form(None),
    lat: float | None = Form(None),
    lon: float | None = Form(None),
    archivos: list[UploadFile] = File(..., description="Foto/firma de la entrega"),
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    current_user: Usuario = Depends(get_current_user),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    """Sube la prueba de entrega (foto/firma) a GridFS y guarda coords/receptor en la asignacion."""
    asignacion = await db.get(Asignacion, asignacion_id)
    if asignacion is None or not _asg_en_alcance(scope, asignacion):
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    entrega = await entregas_service.crear_con_archivos(
        mongo_db,
        asignacion_id=asignacion_id,
        archivos=archivos,
        tipo=tipo,
        descripcion=descripcion,
        lat=lat,
        lon=lon,
        receptor=receptor,
        uploaded_by=current_user.id,
    )
    if lat is not None:
        asignacion.entrega_lat = lat
    if lon is not None:
        asignacion.entrega_lon = lon
    if receptor is not None:
        asignacion.entrega_receptor = receptor
    await db.commit()
    return entrega


@router.get("/{asignacion_id}/prueba-entrega", response_model=list[EntregaOut])
async def list_pruebas_entrega(
    asignacion_id: int,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "read")),
):
    asignacion = await db.get(Asignacion, asignacion_id)
    if asignacion is None or not _asg_en_alcance(scope, asignacion):
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    return await entregas_service.listar_por_asignacion(mongo_db, asignacion_id)


@router.get("/prueba-entrega/archivos/{file_id}")
async def descargar_archivo_entrega(
    file_id: str,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("asignaciones", "read")),
):
    grid_out = await entregas_service.abrir_descarga(mongo_db, file_id)
    if grid_out is None:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    metadata = grid_out.metadata or {}
    content_type = metadata.get("content_type") or "application/octet-stream"

    async def _iter():
        async for chunk in grid_out:
            yield chunk

    return StreamingResponse(
        _iter(),
        media_type=content_type,
        headers={
            "Content-Length": str(grid_out.length),
            "Content-Disposition": f'inline; filename="{grid_out.filename}"',
        },
    )


@router.delete("/{asignacion_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asignacion(
    asignacion_id: int,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("asignaciones", "delete")),
):
    asignacion = await db.get(Asignacion, asignacion_id)
    if asignacion is None:
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    if asignacion.estado == "EnCurso":
        raise HTTPException(status_code=400, detail="No se puede borrar una asignacion en curso")
    await tracking_service.eliminar_por_asignacion(mongo_db, asignacion_id)
    await geocerca_service.eliminar_por_asignacion(mongo_db, asignacion_id)
    await entregas_service.eliminar_por_asignacion(mongo_db, asignacion_id)
    await db.delete(asignacion)
    await db.commit()
