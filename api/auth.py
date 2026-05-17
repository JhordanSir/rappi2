from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.database import get_db
from core.security import verify_password, create_access_token, get_password_hash
from core.config import settings
from models.users import Usuario
from schemas.users import Token, UsuarioCreate, UsuarioResponse, UsuarioUpdate
from api.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

@router.post("/token", response_model=Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Usuario).filter(Usuario.username == form_data.username))
    user = result.scalars().first()
    
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=UsuarioResponse)
async def register_user(user_in: UsuarioCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Usuario).filter((Usuario.username == user_in.username) | (Usuario.email == user_in.email)))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Username or email already registered")
        
    new_user = Usuario(
        username=user_in.username,
        email=user_in.email,
        password_hash=get_password_hash(user_in.password),
        rol_id=user_in.rol_id
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user

@router.get("/users", response_model=list[UsuarioResponse])
async def get_users(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    result = await db.execute(select(Usuario).where(Usuario.is_active == True).offset(skip).limit(limit))
    return result.scalars().all()

@router.patch("/users/{user_id}", response_model=UsuarioResponse)
async def update_user(user_id: int, user_update: UsuarioUpdate, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    result = await db.execute(select(Usuario).where(Usuario.id == user_id, Usuario.is_active == True))
    db_user = result.scalar_one_or_none()
    
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    update_data = user_update.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_user, key, value)
        
    await db.commit()
    await db.refresh(db_user)
    return db_user

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(user_id: int, db: AsyncSession = Depends(get_db), current_user: Usuario = Depends(get_current_user)):
    result = await db.execute(select(Usuario).where(Usuario.id == user_id))
    db_user = result.scalar_one_or_none()
    
    if not db_user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
    db_user.is_active = False
    await db.commit()
    return None
