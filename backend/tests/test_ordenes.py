"""Máquina de estados de órdenes (transiciones vía PATCH/DELETE) y creación por el
rol Cliente sin cliente_id (el backend lo fuerza desde el token — fix del 422)."""
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

import api.ordenes as ordenes_mod
from api.dependencies import get_current_user
from core.database import AsyncSessionLocal
from main import app
from models.roles import Permiso, Rol
from models.usuarios import Usuario


async def test_cliente_crea_orden_sin_cliente_id(client, factoria, db, monkeypatch):
    """El 'Nuevo envío' del cliente no manda cliente_id: antes Pydantic respondía 422;
    ahora el campo es opcional y el endpoint usa el cliente del token."""
    # Cotización usa OSRM externo: se anula para que el test sea hermético.
    async def _sin_cotizar(*args, **kwargs):
        return None
    monkeypatch.setattr(ordenes_mod, "_cotizar_destinos", _sin_cotizar)

    rol_cliente = (await db.execute(select(Rol).where(Rol.nombre == "Cliente"))).scalar_one()
    # El rol Cliente necesita el permiso fino para crear órdenes.
    db.add(Permiso(rol_id=rol_cliente.id, recurso="ordenes", accion="write"))
    ficha = await factoria.cliente()
    u = Usuario(
        username=f"cliuser{ficha.id}", email=f"cliuser{ficha.id}@testmail.com",
        rol_id=rol_cliente.id, cliente_id=ficha.id,
        auth_provider="keycloak", keycloak_sub=f"sub-cli-{ficha.id}",
    )
    db.add(u)
    await db.commit()

    async def _cliente_actual():
        async with AsyncSessionLocal() as s:
            return (
                await s.execute(
                    select(Usuario).options(selectinload(Usuario.rol)).where(Usuario.id == u.id)
                )
            ).scalar_one()

    previo = app.dependency_overrides[get_current_user]
    app.dependency_overrides[get_current_user] = _cliente_actual
    try:
        r = await client.post("/api/ordenes/", json={
            "direccion_origen": "Av. Prueba 100",
            "lat_origen": -16.35, "lon_origen": -71.55,
            "destinos": [{"direccion": "Calle Destino 200", "lat": -16.36, "lon": -71.54, "peso_kg": 3}],
        })
    finally:
        app.dependency_overrides[get_current_user] = previo

    assert r.status_code == 201, r.text
    body = r.json()
    assert body["cliente_id"] == ficha.id  # forzado desde el token, no del payload
    # El paquete físico vive en el destino; la orden expone el AGREGADO derivado y ya no
    # el campo legacy a nivel de orden.
    assert body["destinos"][0]["peso_kg"] == 3
    assert float(body["peso_total_kg"]) == 3.0
    assert "peso_kg" not in body


async def test_staff_sin_cliente_id_da_400(client, monkeypatch):
    """El staff sí debe indicar el cliente: sin cliente_id → 400 claro (no 422 ni 500)."""
    async def _sin_cotizar(*args, **kwargs):
        return None
    monkeypatch.setattr(ordenes_mod, "_cotizar_destinos", _sin_cotizar)
    r = await client.post("/api/ordenes/", json={
        "direccion_origen": "Av. Prueba 100",
        "lat_origen": -16.35, "lon_origen": -71.55,
        "destinos": [{"direccion": "Calle Destino 200", "lat": -16.36, "lon": -71.54}],
    })
    assert r.status_code == 400
    assert "cliente" in r.json()["detail"].lower()


async def test_terminal_no_se_revive(client, factoria):
    cli = await factoria.cliente()
    orden = await factoria.orden(cli.id, estado="Entregado")
    r = await client.patch(f"/api/ordenes/{orden.id}", json={"estado": "Pendiente"})
    assert r.status_code == 409
    assert "ilegal" in r.json()["detail"].lower()


async def test_avance_manual_bloqueado(client, factoria):
    """Los estados de avance solo se alcanzan por sus endpoints (asignar/iniciar), no a mano."""
    cli = await factoria.cliente()
    orden = await factoria.orden(cli.id, estado="Pendiente")
    r = await client.patch(f"/api/ordenes/{orden.id}", json={"estado": "En Tránsito"})
    assert r.status_code == 409


async def test_cancelar_entregada_bloqueado(client, factoria):
    cli = await factoria.cliente()
    orden = await factoria.orden(cli.id, estado="Entregado")
    r = await client.delete(f"/api/ordenes/{orden.id}")
    assert r.status_code == 409


async def test_cancelar_pendiente_ok(client, factoria, db):
    cli = await factoria.cliente()
    orden = await factoria.orden(cli.id, estado="Pendiente")
    r = await client.delete(f"/api/ordenes/{orden.id}")
    assert r.status_code == 204
    await db.refresh(orden)
    assert orden.estado == "Cancelado"


async def test_liberar_pendiente_de_pago(client, factoria, db):
    """'Pendiente de Pago' → 'Pendiente' sí es una transición manual legal (staff)."""
    cli = await factoria.cliente()
    orden = await factoria.orden(cli.id, estado="Pendiente de Pago")
    r = await client.patch(f"/api/ordenes/{orden.id}", json={"estado": "Pendiente"})
    assert r.status_code == 200, r.text
    await db.refresh(orden)
    assert orden.estado == "Pendiente"
