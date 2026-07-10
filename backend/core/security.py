"""Hashing de contraseña para las fichas locales.

La autenticación de la aplicación la provee Keycloak (ver `services/keycloak.py`): el
backend ya NO emite ni valida JWT propios. `hash_password` solo se usa para el hash local
de fallback de usuarios legacy sin `keycloak_sub` y para los datos de demo; no autentica
el acceso a la API (por eso no hay `verify_password`: no existe login local).
"""
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)
