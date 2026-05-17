from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from geoalchemy2.elements import WKTElement

from core.database import get_db
from models.clientes import Cliente, ClienteDireccion
from models.users import Usuario
from schemas.clientes import ClienteCreate, ClienteResponse, ClienteDireccionCreate, ClienteDireccionResponse, ClienteUpdate
from api.dependencies import get_current_user

router = APIRouter(prefix="/clientes", tags=["clientes"])

@router.post("/", response_model=ClienteResponse)
async def create_cliente(cliente_in: ClienteCreate, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    new_cliente = Cliente(**cliente_in.model_dump())
    db.add(new_cliente)
    await db.commit()
    await db.refresh(new_cliente)
    return new_cliente

@router.get("/", response_model=list[ClienteResponse])
async def list_clientes(skip: int = 0, limit: int = 10, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    result = await db.execute(select(Cliente).where(Cliente.is_active == True).options(selectinload(Cliente.direcciones)).offset(skip).limit(limit))
    return result.scalars().all()

@router.patch("/{cliente_id}", response_model=ClienteResponse)
async def update_cliente(cliente_id: int, cliente_update: ClienteUpdate, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    result = await db.execute(select(Cliente).where(Cliente.id == cliente_id, Cliente.is_active == True))
    db_cliente = result.scalar_one_or_none()
    
    if not db_cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
        
    update_data = cliente_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_cliente, key, value)
        
    await db.commit()
    await db.refresh(db_cliente)
    return db_cliente

@router.delete("/{cliente_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_cliente(cliente_id: int, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    result = await db.execute(select(Cliente).where(Cliente.id == cliente_id))
    db_cliente = result.scalar_one_or_none()
    
    if not db_cliente:
        raise HTTPException(status_code=404, detail="Cliente no encontrado")
        
    db_cliente.is_active = False
    await db.commit()
    return None

@router.post("/{cliente_id}/direcciones", response_model=ClienteDireccionResponse)
async def add_cliente_direccion(cliente_id: int, dir_in: ClienteDireccionCreate, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    # Check if client exists
    result = await db.execute(select(Cliente).filter(Cliente.id == cliente_id))
    cliente = result.scalars().first()
    if not cliente:
        raise HTTPException(status_code=404, detail="Cliente not found")
        
    # Convert lat/lon to PostGIS geometry WKT (POINT(lon lat))
    point_wkt = f"POINT({dir_in.longitud} {dir_in.latitud})"
    geom = WKTElement(point_wkt, srid=4326)
    
    new_dir = ClienteDireccion(
        cliente_id=cliente_id,
        geom=geom,
        direccion_texto=dir_in.direccion_texto,
        ciudad=dir_in.ciudad,
        estado=dir_in.estado,
        cp=dir_in.cp,
        es_principal=dir_in.es_principal
    )
    db.add(new_dir)
    await db.commit()
    await db.refresh(new_dir)
    
    return new_dir
