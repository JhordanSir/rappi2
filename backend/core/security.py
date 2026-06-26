"""Utilidades de contraseña para las fichas locales.

La autenticación de la aplicación la provee Keycloak (ver `services/keycloak.py`): el
backend ya NO emite ni valida JWT propios. Estas funciones solo se usan para fichas de
usuario administradas localmente (alta de staff por un admin, datos de demo); no
autentican el acceso a la API.
"""
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)
