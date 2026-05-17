from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from core.database import get_db
from models.logistica import Vehiculo, Conductor
from schemas.logistica import VehiculoCreate, VehiculoResponse, ConductorCreate, ConductorResponse
from schemas.logistica_update import VehiculoUpdate, ConductorUpdate
from api.dependencies import get_current_user
from models.users import Usuario

router = APIRouter(tags=["Logistica"])

@router.post("/vehiculos/", response_model=VehiculoResponse, status_code=status.HTTP_201_CREATED)
async def create_vehiculo(vehiculo: VehiculoCreate, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    db_vehiculo = Vehiculo(**vehiculo.model_dump())

    db.add(db_vehiculo)
    try:
        await db.commit()
        await db.refresh(db_vehiculo)
        return db_vehiculo
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Error creando vehículo. Verifique la placa.")

@router.get("/vehiculos/", response_model=list[VehiculoResponse])
async def get_vehiculos(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    result = await db.execute(select(Vehiculo).where(Vehiculo.is_active == True).offset(skip).limit(limit))
    return result.scalars().all()

@router.patch("/vehiculos/{vehiculo_id}", response_model=VehiculoResponse)
async def update_vehiculo(vehiculo_id: int, vehiculo_update: VehiculoUpdate, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    """Actualiza parcialmente los datos de un vehículo."""
    result = await db.execute(select(Vehiculo).where(Vehiculo.id == vehiculo_id, Vehiculo.is_active == True))
    db_vehiculo = result.scalar_one_or_none()
    
    if not db_vehiculo:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado o inactivo")
        
    update_data = vehiculo_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_vehiculo, key, value)
        
    await db.commit()
    await db.refresh(db_vehiculo)
    return db_vehiculo

@router.delete("/vehiculos/{vehiculo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vehiculo(vehiculo_id: int, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    """Eliminado lógico de un vehículo (is_active = False)."""
    result = await db.execute(select(Vehiculo).where(Vehiculo.id == vehiculo_id))
    db_vehiculo = result.scalar_one_or_none()
    
    if not db_vehiculo:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
        
    db_vehiculo.is_active = False
    await db.commit()
    return None

@router.post("/conductores/", response_model=ConductorResponse, status_code=status.HTTP_201_CREATED)
async def create_conductor(conductor: ConductorCreate, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    db_conductor = Conductor(**conductor.model_dump())
    db.add(db_conductor)
    try:
        await db.commit()
        await db.refresh(db_conductor)
        return db_conductor
    except Exception as e:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Error creando conductor. Verifique usuario_id y licencia.")

@router.get("/conductores/", response_model=list[ConductorResponse])
async def get_conductores(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    result = await db.execute(select(Conductor).where(Conductor.is_active == True).offset(skip).limit(limit))
    return result.scalars().all()

@router.patch("/conductores/{conductor_id}", response_model=ConductorResponse)
async def update_conductor(conductor_id: int, conductor_update: ConductorUpdate, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    """Actualiza parcialmente los datos de un conductor."""
    result = await db.execute(select(Conductor).where(Conductor.id == conductor_id, Conductor.is_active == True))
    db_conductor = result.scalar_one_or_none()
    
    if not db_conductor:
        raise HTTPException(status_code=404, detail="Conductor no encontrado o inactivo")
        
    update_data = conductor_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_conductor, key, value)
        
    await db.commit()
    await db.refresh(db_conductor)
    return db_conductor

@router.delete("/conductores/{conductor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conductor(conductor_id: int, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    """Eliminado lógico de un conductor (is_active = False)."""
    result = await db.execute(select(Conductor).where(Conductor.id == conductor_id))
    db_conductor = result.scalar_one_or_none()
    
    if not db_conductor:
        raise HTTPException(status_code=404, detail="Conductor no encontrado")
        
    db_conductor.is_active = False
    await db.commit()
    return None
