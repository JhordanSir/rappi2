from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.dependencies import get_current_user, get_mongo_db, require_permiso
from core.database import get_db
from models.asignaciones import Asignacion
from models.incidencias import Incidencia
from models.usuarios import Usuario
from schemas.common import TipoEvidencia
from schemas.incidencias import IncidenciaCreate, IncidenciaResponse, IncidenciaUpdate
from schemas.mongo_evidencias import EvidenciaIn, EvidenciaOut
from services.mongo import evidencias_service

router = APIRouter(prefix="/incidencias", tags=["incidencias"])


@router.get("/", response_model=list[IncidenciaResponse])
async def list_incidencias(
    skip: int = 0,
    limit: int = Query(50, le=200),
    asignacion_id: int | None = None,
    severidad_min: int | None = None,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("incidencias", "read")),
):
    stmt = select(Incidencia)
    if asignacion_id is not None:
        stmt = stmt.where(Incidencia.asignacion_id == asignacion_id)
    if severidad_min is not None:
        stmt = stmt.where(Incidencia.severidad >= severidad_min)
    stmt = stmt.order_by(Incidencia.fecha.desc()).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/", response_model=IncidenciaResponse, status_code=status.HTTP_201_CREATED)
async def create_incidencia(
    payload: IncidenciaCreate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("incidencias", "write")),
):
    asignacion = await db.get(Asignacion, payload.asignacion_id)
    if asignacion is None:
        raise HTTPException(status_code=400, detail="asignacion_id invalido")
    incidencia = Incidencia(**payload.model_dump())
    db.add(incidencia)
    await db.commit()
    await db.refresh(incidencia)
    return incidencia


@router.get("/{incidencia_id}", response_model=IncidenciaResponse)
async def get_incidencia(
    incidencia_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("incidencias", "read")),
):
    incidencia = await db.get(Incidencia, incidencia_id)
    if incidencia is None:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")
    return incidencia


@router.patch("/{incidencia_id}", response_model=IncidenciaResponse)
async def update_incidencia(
    incidencia_id: int,
    payload: IncidenciaUpdate,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("incidencias", "write")),
):
    incidencia = await db.get(Incidencia, incidencia_id)
    if incidencia is None:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(incidencia, k, v)
    await db.commit()
    await db.refresh(incidencia)
    return incidencia


@router.delete("/{incidencia_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_incidencia(
    incidencia_id: int,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("incidencias", "delete")),
):
    incidencia = await db.get(Incidencia, incidencia_id)
    if incidencia is None:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")
    await evidencias_service.eliminar_por_incidencia(mongo_db, incidencia_id)
    await db.delete(incidencia)
    await db.commit()


@router.post("/{incidencia_id}/evidencias", response_model=EvidenciaOut, status_code=status.HTTP_201_CREATED)
async def add_evidencia(
    incidencia_id: int,
    payload: EvidenciaIn,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    current_user: Usuario = Depends(get_current_user),
    _: object = Depends(require_permiso("incidencias", "write")),
):
    incidencia = await db.get(Incidencia, incidencia_id)
    if incidencia is None:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")
    doc = await evidencias_service.crear(mongo_db, incidencia_id, payload, current_user.id)
    return doc


@router.post(
    "/{incidencia_id}/evidencias/upload",
    response_model=EvidenciaOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_evidencia(
    incidencia_id: int,
    tipo: TipoEvidencia = Form(...),
    descripcion: str | None = Form(None),
    archivos: list[UploadFile] = File(..., description="Uno o mas archivos (foto/video/audio/documento)"),
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    current_user: Usuario = Depends(get_current_user),
    _: object = Depends(require_permiso("incidencias", "write")),
):
    """Sube archivos fisicos a GridFS y crea el documento de evidencia asociado."""
    incidencia = await db.get(Incidencia, incidencia_id)
    if incidencia is None:
        raise HTTPException(status_code=404, detail="Incidencia no encontrada")
    return await evidencias_service.crear_con_archivos(
        mongo_db,
        incidencia_id=incidencia_id,
        archivos=archivos,
        tipo=tipo,
        descripcion=descripcion,
        uploaded_by=current_user.id,
    )


@router.get("/evidencias/archivos/{file_id}")
async def descargar_archivo_evidencia(
    file_id: str,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("incidencias", "read")),
):
    grid_out = await evidencias_service.abrir_descarga(mongo_db, file_id)
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


@router.get("/{incidencia_id}/evidencias", response_model=list[EvidenciaOut])
async def list_evidencias(
    incidencia_id: int,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("incidencias", "read")),
):
    return await evidencias_service.listar_por_incidencia(mongo_db, incidencia_id)


@router.get("/evidencias/{evidencia_id}", response_model=EvidenciaOut)
async def get_evidencia(
    evidencia_id: str,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("incidencias", "read")),
):
    doc = await evidencias_service.obtener(mongo_db, evidencia_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Evidencia no encontrada")
    return doc


@router.delete("/evidencias/{evidencia_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_evidencia(
    evidencia_id: str,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("incidencias", "delete")),
):
    ok = await evidencias_service.eliminar(mongo_db, evidencia_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Evidencia no encontrada")
