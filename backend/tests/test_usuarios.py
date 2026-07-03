"""Ciclo de vida de usuarios: creación federada en Keycloak (espejo local con sub),
soft-delete, re-registro con el mismo correo (409 claro) y reactivación por el admin
con cascada a las fichas Cliente/Conductor."""
import uuid

import pytest
from sqlalchemy.future import select

from models.clientes import Cliente
from models.roles import Rol
from models.usuarios import Usuario
from services import keycloak_admin


@pytest.fixture(autouse=True)
def _keycloak_admin_fake(monkeypatch):
    """La gestión de usuarios habla con la Admin API de Keycloak; aquí se simula
    (sub aleatorio, operaciones no-op) para no depender del servidor ni ensuciar
    el realm. La integración real se verifica E2E contra el Keycloak local."""

    async def _crear(username, email, password, rol):
        return str(uuid.uuid4())

    async def _nada(*args, **kwargs):
        return None

    monkeypatch.setattr(keycloak_admin, "crear_usuario", _crear)
    monkeypatch.setattr(keycloak_admin, "actualizar", _nada)
    monkeypatch.setattr(keycloak_admin, "reset_password", _nada)
    monkeypatch.setattr(keycloak_admin, "asignar_rol", _nada)
    monkeypatch.setattr(keycloak_admin, "eliminar", _nada)


async def _rol_id(db, nombre: str) -> int:
    return (await db.execute(select(Rol).where(Rol.nombre == nombre))).scalar_one().id


async def test_recrear_correo_inactivo_da_409_y_reactivar_revive_ficha(client, factoria, db):
    rol_cliente = await _rol_id(db, "Cliente")
    body = {
        "username": "walter_test",
        "email": "walter@testmail.com",
        "password": "Secreta123!",
        "rol_id": rol_cliente,
    }
    creado = await client.post("/api/usuarios/", json=body)
    assert creado.status_code == 201, creado.text
    uid = creado.json()["id"]
    cliente_id = creado.json()["cliente_id"]
    assert cliente_id is not None  # rol Cliente ⇒ ficha enlazada

    # El espejo local queda federado: sub de Keycloak y SIN hash local (la credencial
    # vive en Keycloak).
    u = (await db.execute(select(Usuario).where(Usuario.id == uid))).scalar_one()
    assert u.keycloak_sub is not None
    assert u.auth_provider == "keycloak"
    assert u.password_hash is None

    # Soft-delete: usuario y ficha quedan inactivos.
    assert (await client.delete(f"/api/usuarios/{uid}")).status_code == 204
    ficha = (await db.execute(select(Cliente).where(Cliente.id == cliente_id))).scalar_one()
    assert ficha.activo is False

    # Re-registro con el mismo correo: mensaje accionable, no un "ya en uso" genérico.
    r = await client.post("/api/usuarios/", json={**body, "username": "walter_test2"})
    assert r.status_code == 409
    assert "inactivo" in r.json()["detail"]

    # Solo el admin reactiva; la ficha Cliente revive en cascada.
    r = await client.patch(f"/api/usuarios/{uid}", json={"activo": True})
    assert r.status_code == 200, r.text
    await db.refresh(ficha)
    assert ficha.activo is True


async def test_reactivar_conductor_exige_usuario_activo(client, factoria, db):
    cond = await factoria.conductor()
    # Baja del conductor (cascada: usuario inactivo).
    assert (await client.delete(f"/api/conductores/{cond.id}")).status_code == 204

    # Reactivar la ficha con el usuario aún inactivo → 409 con instrucción clara.
    r = await client.patch(f"/api/conductores/{cond.id}", json={"activo": True})
    assert r.status_code == 409
    assert "Reactívalo primero" in r.json()["detail"]

    # Reactivar el usuario revive la ficha (cascada de provisioning).
    r = await client.patch(f"/api/usuarios/{cond.usuario_id}", json={"activo": True})
    assert r.status_code == 200, r.text
    await db.refresh(cond)
    assert cond.activo is True
    assert cond.disponibilidad == "Disponible"
