"""Roles personalizados (Despachador/Auditor…): se sincronizan como realm-role en
Keycloak, el login NO degrada al usuario a Cliente y su alcance es de staff."""
import pytest
from sqlalchemy.future import select

from api.dependencies import es_staff_rol
from models.roles import Rol
from services import keycloak_admin
from services.provisioning import ensure_usuario_from_claims


@pytest.fixture(autouse=True)
def _keycloak_admin_fake(monkeypatch):
    """Simula la Admin API (registra llamadas) para no depender del servidor real."""
    llamadas = {"asegurar": []}

    async def _asegurar(nombre, descripcion=None):
        llamadas["asegurar"].append(nombre)
        return {"name": nombre}

    async def _nada(*args, **kwargs):
        return None

    monkeypatch.setattr(keycloak_admin, "asegurar_rol_realm", _asegurar)
    monkeypatch.setattr(keycloak_admin, "eliminar_rol_realm", _nada)
    monkeypatch.setattr(keycloak_admin, "renombrar_rol_realm", _nada)
    return llamadas


async def test_crear_rol_sincroniza_realm(client, _keycloak_admin_fake):
    r = await client.post("/api/roles/", json={"nombre": "Despachador"})
    assert r.status_code == 201, r.text
    # El rol también se creó como realm-role en Keycloak (si no, sería invisible al token).
    assert "Despachador" in _keycloak_admin_fake["asegurar"]


async def test_login_no_degrada_rol_custom(db):
    """Un token con realm-role 'Despachador' conserva el rol local (antes cada login
    lo sobreescribía a Cliente y le creaba ficha de cliente)."""
    rol = (await db.execute(select(Rol).where(Rol.nombre == "Despachador"))).scalar_one_or_none()
    if rol is None:
        rol = Rol(nombre="Despachador")
        db.add(rol)
        await db.commit()
        await db.refresh(rol)

    claims = {
        "sub": "sub-despachador-1",
        "email": "despa1@testmail.com",
        "preferred_username": "despa1",
        "realm_access": {"roles": ["Despachador", "offline_access", "default-roles-rappi2"]},
    }
    user = await ensure_usuario_from_claims(db, claims)
    await db.commit()
    assert user.rol.nombre == "Despachador"  # NO degradado a Cliente
    assert user.cliente_id is None           # staff: sin ficha de cliente

    # Segundo login: idempotente, sigue con su rol.
    user2 = await ensure_usuario_from_claims(db, claims)
    await db.commit()
    assert user2.rol_id == rol.id


def test_es_staff_rol():
    assert es_staff_rol("Admin") is True
    assert es_staff_rol("Despachador") is True   # rol custom = staff (panel operativo)
    assert es_staff_rol("Cliente") is False
    assert es_staff_rol("Conductor") is False
    assert es_staff_rol(None) is False
