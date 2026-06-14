from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.dependencies import get_current_user, get_mongo_db, require_permiso
from core.database import get_db
from models.asignaciones import Asignacion
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
)
from schemas.common import TipoEvidencia
from services.mongo import entregas_service, geocerca_service, tracking_service

router = APIRouter(prefix="/asignaciones", tags=["asignaciones"])


@router.get("/", response_model=list[AsignacionResponse])
async def list_asignaciones(
    skip: int = 0,
    limit: int = Query(50, le=200),
    estado: str | None = None,
    conductor_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("asignaciones", "read")),
):
    stmt = select(Asignacion)
    if estado is not None:
        stmt = stmt.where(Asignacion.estado == estado)
    if conductor_id is not None:
        stmt = stmt.where(Asignacion.conductor_id == conductor_id)
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=AsignacionResponse, status_code=status.HTTP_201_CREATED)
async def create_asignacion(
    payload: AsignacionCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
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


@router.get("/{asignacion_id}", response_model=AsignacionResponse)
async def get_asignacion(
    asignacion_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("asignaciones", "read")),
):
    asignacion = await db.get(Asignacion, asignacion_id)
    if asignacion is None:
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    return asignacion


@router.patch("/{asignacion_id}", response_model=AsignacionResponse)
async def update_asignacion(
    asignacion_id: int,
    payload: AsignacionUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
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
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    asignacion = await db.get(Asignacion, asignacion_id)
    if asignacion is None:
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
    return asignacion


@router.patch("/{asignacion_id}/finalizar", response_model=AsignacionResponse)
async def finalizar_asignacion(
    asignacion_id: int,
    payload: FinalizarAsignacionRequest | None = None,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    asignacion = await db.get(Asignacion, asignacion_id)
    if asignacion is None:
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
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    """Sube la prueba de entrega (foto/firma) a GridFS y guarda coords/receptor en la asignacion."""
    asignacion = await db.get(Asignacion, asignacion_id)
    if asignacion is None:
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
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("asignaciones", "read")),
):
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
