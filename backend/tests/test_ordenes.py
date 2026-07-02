"""Máquina de estados de órdenes: transiciones legales e ilegales vía PATCH/DELETE."""


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
