"""Pago manual del staff: monto contra el total, sin duplicados, y liberación de la
orden retenida por pago."""


async def test_monto_debe_coincidir_con_total(client, factoria):
    cli = await factoria.cliente()
    orden = await factoria.orden(cli.id, total=100)
    r = await client.post(f"/api/ordenes/{orden.id}/pagos", json={"monto": 90, "estado": "Pagado"})
    assert r.status_code == 400
    assert "no coincide" in r.json()["detail"]


async def test_no_duplicar_pago_confirmado(client, factoria):
    cli = await factoria.cliente()
    orden = await factoria.orden(cli.id, total=100)
    r1 = await client.post(f"/api/ordenes/{orden.id}/pagos", json={"monto": 100, "estado": "Pagado"})
    assert r1.status_code == 201, r1.text
    r2 = await client.post(f"/api/ordenes/{orden.id}/pagos", json={"monto": 100, "estado": "Pagado"})
    assert r2.status_code == 409
    assert "ya tiene un pago confirmado" in r2.json()["detail"]


async def test_pago_confirmado_libera_orden_retenida(client, factoria, db):
    cli = await factoria.cliente()
    orden = await factoria.orden(cli.id, estado="Pendiente de Pago", total=50)
    r = await client.post(f"/api/ordenes/{orden.id}/pagos", json={"monto": 50, "estado": "Pagado"})
    assert r.status_code == 201, r.text
    await db.refresh(orden)
    assert orden.estado == "Pendiente"  # despachable


async def test_no_pagar_orden_cancelada(client, factoria):
    cli = await factoria.cliente()
    orden = await factoria.orden(cli.id, estado="Cancelado", total=50)
    r = await client.post(f"/api/ordenes/{orden.id}/pagos", json={"monto": 50, "estado": "Pagado"})
    assert r.status_code == 409
