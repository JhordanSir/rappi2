from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from core.database import get_db
from core.security import verify_password, create_access_token, get_password_hash
from core.config import settings
from models.users import Usuario
from schemas.users import Token, UsuarioCreate, UsuarioResponse

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
