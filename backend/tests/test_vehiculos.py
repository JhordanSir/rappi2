"""Vehículos: dimensiones obligatorias al crear y no anulables al editar (cubicaje)."""


async def test_crear_sin_dimensiones_rechazado(client):
    r = await client.post(
        "/api/vehiculos/",
        json={"placa": "TST-901", "tipo": "Moto", "capacidad_kg": 50},
    )
    assert r.status_code == 422


async def test_crear_con_dimensiones_ok(client):
    r = await client.post(
        "/api/vehiculos/",
        json={
            "placa": "TST-902", "tipo": "Moto", "capacidad_kg": 50,
            "largo_cm": 40, "ancho_cm": 40, "alto_cm": 40,
        },
    )
    assert r.status_code == 201, r.text


async def test_editar_no_permite_vaciar_dimensiones(client, factoria):
    veh = await factoria.vehiculo()
    r = await client.patch(f"/api/vehiculos/{veh.placa}", json={"largo_cm": None})
    assert r.status_code == 422
    r = await client.patch(f"/api/vehiculos/{veh.placa}", json={"ancho_cm": -5})
    assert r.status_code == 422
