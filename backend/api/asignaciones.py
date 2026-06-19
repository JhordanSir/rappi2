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
from models.asignaciones import Asignacion
from models.calificaciones import Calificacion
from models.conductores import Conductor
from models.ordenes import Orden
from models.usuarios import Usuario
from models.vehiculos import Vehiculo
from schemas.asignaciones import (
    AsignacionCreate,
    AsignacionResponse,
    AsignacionUpdate,
    EntregaOut,
    FinalizarAsignacionRequest,
    SugerenciaConductor,
)
from schemas.common import TipoEvidencia
from services.mongo import entregas_service, geocerca_service, tracking_service
from services.mongo.tracking_service import _haversine_m

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


@router.post("/", response_model=AsignacionResponse, status_code=status.HTTP_201_CREATED)
async def create_asignacion(
    payload: AsignacionCreate,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    _solo_staff(scope)
    orden = await db.get(Orden, payload.orden_id)
    if orden is None:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    if orden.estado != "Pendiente":
        raise HTTPException(status_code=400, detail=f"Orden no esta Pendiente (estado actual: {orden.estado})")

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

    asignacion = Asignacion(**payload.model_dump(), estado="Asignada")
    db.add(asignacion)
    orden.estado = "En Proceso"
    conductor.disponibilidad = "Ocupado"
    await db.commit()
    await db.refresh(asignacion)
    return asignacion


@router.get("/sugerencia", response_model=list[SugerenciaConductor])
async def sugerir_conductor(
    orden_id: int,
    limit: int = Query(5, le=20),
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "read")),
):
    """Sugiere los mejores conductores para una orden: disponibles, con vehículo
    operativo, ordenados por cercanía al origen (última posición GPS) y rating.
    El despachador confirma creando la asignación con POST /asignaciones/."""
    _solo_staff(scope)
    orden = await db.get(Orden, orden_id)
    if orden is None:
        raise HTTPException(status_code=404, detail="Orden no encontrada")

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

    lon_o = float(orden.lon_origen) if orden.lon_origen is not None else None
    lat_o = float(orden.lat_origen) if orden.lat_origen is not None else None

    sugerencias: list[SugerenciaConductor] = []
    for cond, _veh in rows:
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
        sugerencias.append(
            SugerenciaConductor(
                conductor_id=cond.id,
                nombre=cond.nombre,
                vehiculo_placa=cond.vehiculo_placa,
                distancia_km=dist_km,
                rating=round(float(prom), 2) if prom is not None else None,
                total_calificaciones=total or 0,
            )
        )

    # Más cercano primero; los sin posición conocida al final; desempate por mejor rating.
    sugerencias.sort(key=lambda s: (s.distancia_km is None, s.distancia_km or 0.0, -(s.rating or 0.0)))
    return sugerencias[:limit]


@router.get("/{asignacion_id}", response_model=AsignacionResponse)
async def get_asignacion(
    asignacion_id: int,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "read")),
):
    asignacion = await db.get(Asignacion, asignacion_id)
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
    asignacion = await db.get(Asignacion, asignacion_id)
    if asignacion is None or not _asg_en_alcance(scope, asignacion):
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    if asignacion.estado != "Asignada":
        raise HTTPException(status_code=400, detail=f"Asignacion no esta Asignada (actual: {asignacion.estado})")
    orden = await db.get(Orden, asignacion.orden_id)
    asignacion.estado = "EnCurso"
    asignacion.fecha_inicio = datetime.now(timezone.utc)
    if orden is not None:
        orden.estado = "En Tránsito"
    await db.commit()
    await db.refresh(asignacion)
    await _avisar_estado_orden(db, orden)
    return asignacion


@router.patch("/{asignacion_id}/finalizar", response_model=AsignacionResponse)
async def finalizar_asignacion(
    asignacion_id: int,
    payload: FinalizarAsignacionRequest | None = None,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    asignacion = await db.get(Asignacion, asignacion_id)
    if asignacion is None or not _asg_en_alcance(scope, asignacion):
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    if asignacion.estado != "EnCurso":
        raise HTTPException(status_code=400, detail=f"Asignacion no esta EnCurso (actual: {asignacion.estado})")
    orden = await db.get(Orden, asignacion.orden_id)
    conductor = await db.get(Conductor, asignacion.conductor_id)
    asignacion.estado = "Finalizada"
    asignacion.fecha_fin = datetime.now(timezone.utc)
    if payload is not None:
        if payload.lat is not None:
            asignacion.entrega_lat = payload.lat
        if payload.lon is not None:
            asignacion.entrega_lon = payload.lon
        if payload.receptor is not None:
            asignacion.entrega_receptor = payload.receptor
    if orden is not None:
        orden.estado = "Entregado"
    if conductor is not None:
        conductor.disponibilidad = "Disponible"
    await db.commit()
    await db.refresh(asignacion)
    await _avisar_estado_orden(db, orden)
    return asignacion


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
