from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from geoalchemy2.elements import WKTElement
import json
from datetime import timedelta

from core.database import get_db
from models.ordenes import Orden, Asignacion, RutaPlanificada
from schemas.ordenes import OrdenCreate, OrdenResponse, AsignacionCreate, AsignacionResponse, OrdenUpdate
from services.ors_service import ors_service
from api.dependencies import get_current_user
from models.users import Usuario

router = APIRouter(tags=["Ordenes"])

@router.post("/ordenes/", response_model=OrdenResponse, status_code=status.HTTP_201_CREATED)
async def create_orden(orden: OrdenCreate, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    # Convertir Coordenada a WKT
    origen_wkt = f"POINT({orden.origen.lon} {orden.origen.lat})"
    destino_wkt = f"POINT({orden.destino.lon} {orden.destino.lat})"
    
    db_orden = Orden(
        cliente_id=orden.cliente_id,
        origen_geom=WKTElement(origen_wkt, srid=4326),
        destino_geom=WKTElement(destino_wkt, srid=4326),
        origen_texto=orden.origen_texto,
        destino_texto=orden.destino_texto,
        estado="Pendiente"
    )
    db.add(db_orden)
    try:
        await db.commit()
        await db.refresh(db_orden)
        return db_orden
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/ordenes/", response_model=list[OrdenResponse])
async def get_ordenes(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    """Obtiene la lista de órdenes paginada."""
    result = await db.execute(select(Orden).offset(skip).limit(limit))
    return result.scalars().all()

@router.get("/ordenes/{orden_id}", response_model=OrdenResponse)
async def get_orden(orden_id: int, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    """Obtiene el detalle de una orden por su ID."""
    result = await db.execute(select(Orden).where(Orden.id == orden_id))
    db_orden = result.scalar_one_or_none()
    if not db_orden:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    return db_orden

@router.patch("/ordenes/{orden_id}", response_model=OrdenResponse)
async def update_orden(orden_id: int, orden_update: OrdenUpdate, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    """Actualiza parcialmente los datos de una orden (estado y textos)."""
    result = await db.execute(select(Orden).where(Orden.id == orden_id))
    db_orden = result.scalar_one_or_none()
    
    if not db_orden:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
        
    update_data = orden_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_orden, key, value)
        
    await db.commit()
    await db.refresh(db_orden)
    return db_orden

@router.delete("/ordenes/{orden_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_orden(orden_id: int, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    """Eliminado lógico de una orden (Cambia el estado a Cancelado)."""
    result = await db.execute(select(Orden).where(Orden.id == orden_id))
    db_orden = result.scalar_one_or_none()
    
    if not db_orden:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
        
    if db_orden.estado == "Cancelado":
        raise HTTPException(status_code=400, detail="La orden ya se encuentra cancelada")

    db_orden.estado = "Cancelado"
    await db.commit()
    return None

@router.post("/asignaciones/", response_model=AsignacionResponse, status_code=status.HTTP_201_CREATED)
async def create_asignacion(asignacion: AsignacionCreate, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    # 1. Verificar orden
    orden_result = await db.execute(select(Orden).where(Orden.id == asignacion.orden_id))
    db_orden = orden_result.scalar_one_or_none()
    if not db_orden:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    
    if db_orden.estado != "Pendiente":
        raise HTTPException(status_code=400, detail="La orden no está pendiente")

    # 2. Crear Asignación
    db_asignacion = Asignacion(
        orden_id=asignacion.orden_id,
        conductor_id=asignacion.conductor_id,
        vehiculo_id=asignacion.vehiculo_id,
        estado="Asignado"
    )
    db.add(db_asignacion)

    # Actualizar estado de orden
    db_orden.estado = "En Proceso"

    # 3. Llamar a OpenRouteService
    try:
        # Obtenemos coords de la orden, para usarlas las extraemos usando func nativas
        # En vez de func, ya que la orden fue recién consultada pero las geometry no son fáciles de extraer,
        # podríamos extraerlas usando una query ST_X y ST_Y
        from sqlalchemy import func
        coords_query = await db.execute(
            select(
                func.ST_X(db_orden.origen_geom), func.ST_Y(db_orden.origen_geom),
                func.ST_X(db_orden.destino_geom), func.ST_Y(db_orden.destino_geom)
            )
        )
        lon_o, lat_o, lon_d, lat_d = coords_query.first()
        
        route_data = await ors_service.get_route(lon_o, lat_o, lon_d, lat_d)
        
        # 4. Generar la línea WKT de la ruta devuelta por ORS
        geometry_json = route_data["geometry"]
        coords = geometry_json["coordinates"]
        
        if len(coords) >= 2:
            linestring_wkt = "LINESTRING(" + ", ".join([f"{lon} {lat}" for lon, lat in coords]) + ")"
        else:
            raise Exception("ORS no devolvió suficientes coordenadas")

        tiempo_est = timedelta(seconds=route_data["tiempo_segundos"])

        db_ruta = RutaPlanificada(
            orden_id=asignacion.orden_id,
            ruta_linea=WKTElement(linestring_wkt, srid=4326),
            tolerancia_metros=50,
            distancia_km=route_data["distancia_km"],
            tiempo_estimado=tiempo_est
        )
        db.add(db_ruta)
        
        await db.commit()
        await db.refresh(db_asignacion)
        await db.refresh(db_ruta)
        
        # Actualizar el geocerca_poligono usando la funcion ST_Buffer de PostGIS (métrica de distancia en geografía)
        from sqlalchemy import text
        await db.execute(
            text("UPDATE rutas_planificadas SET geocerca_poligono = ST_Buffer(ruta_linea::geography, tolerancia_metros)::geometry WHERE id = :id"),
            {"id": db_ruta.id}
        )
        await db.commit()

        return db_asignacion

    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Error en planificación de ruta: {str(e)}")
