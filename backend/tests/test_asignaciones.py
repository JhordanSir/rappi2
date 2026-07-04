"""Asignaciones: validaciones al crear (disponibilidad, carga acumulada) y la
liberación de recursos al cancelar órdenes o eliminar la asignación."""
import pytest
from sqlalchemy.future import select

import api.asignaciones as asg_mod
from models.asignaciones import Asignacion
from models.destinos import Destino


@pytest.fixture(autouse=True)
def _sin_servicios_externos(monkeypatch):
    """Aísla la lógica de negocio: plaqueo sin restricciones y ruta no-op (sin OSRM/Mongo geo)."""

    async def _plaqueo_ok(db, mongo_db, ordenes, placa):
        return {"bloquear": None, "reroute": False}

    async def _ruta_noop(*args, **kwargs):
        return None

    monkeypatch.setattr(asg_mod.plaqueo_service, "evaluar_asignacion", _plaqueo_ok)
    monkeypatch.setattr(asg_mod, "generar_run", _ruta_noop)


async def _asignar(client, orden_id, conductor_id, placa):
    return await client.post(
        "/api/asignaciones/",
        json={"orden_ids": [orden_id], "conductor_id": conductor_id, "vehiculo_placa": placa},
    )


async def test_asignar_actualiza_estados(client, factoria, db):
    cli = await factoria.cliente()
    veh = await factoria.vehiculo()
    cond = await factoria.conductor()
    orden = await factoria.orden(cli.id)

    r = await _asignar(client, orden.id, cond.id, veh.placa)
    assert r.status_code == 201, r.text

    await db.refresh(orden)
    await db.refresh(cond)
    assert orden.estado == "En Proceso"
    assert cond.disponibilidad == "Ocupado"


async def test_conductor_ocupado_no_se_reasigna(client, factoria):
    cli = await factoria.cliente()
    veh = await factoria.vehiculo()
    cond = await factoria.conductor()
    o1 = await factoria.orden(cli.id)
    o2 = await factoria.orden(cli.id)

    assert (await _asignar(client, o1.id, cond.id, veh.placa)).status_code == 201
    r = await _asignar(client, o2.id, cond.id, veh.placa)
    assert r.status_code == 400
    assert "no disponible" in r.json()["detail"].lower()


async def test_carga_acumulada_del_vehiculo(client, factoria):
    """Dos runs activos sobre el MISMO vehículo no pueden exceder su capacidad."""
    cli = await factoria.cliente()
    veh = await factoria.vehiculo(capacidad_kg=100)
    c1 = await factoria.conductor()
    c2 = await factoria.conductor()
    pesada = await factoria.orden(cli.id, peso_kg=70)
    liviana = await factoria.orden(cli.id, peso_kg=50)

    assert (await _asignar(client, pesada.id, c1.id, veh.placa)).status_code == 201
    r = await _asignar(client, liviana.id, c2.id, veh.placa)
    assert r.status_code == 409
    assert "ya lleva" in r.json()["detail"]


async def test_cancelar_orden_libera_conductor_y_asignacion(client, factoria, db):
    cli = await factoria.cliente()
    veh = await factoria.vehiculo()
    cond = await factoria.conductor()
    orden = await factoria.orden(cli.id)
    asg_id = (await _asignar(client, orden.id, cond.id, veh.placa)).json()["id"]

    r = await client.delete(f"/api/ordenes/{orden.id}")
    assert r.status_code == 204, r.text

    await db.refresh(orden)
    await db.refresh(cond)
    asignacion = (await db.execute(select(Asignacion).where(Asignacion.id == asg_id))).scalar_one()
    assert orden.estado == "Cancelado"
    assert asignacion.estado == "Cancelada"
    assert cond.disponibilidad == "Disponible"


async def test_reabrir_run_entregado_requiere_flag(client, factoria, db):
    """Reabrir un run 100% entregado sin el flag deja al conductor sin nada que
    re-ejecutar → 400 con instrucción; con `reabrir_entregados` el destino vuelve a
    Pendiente y el flujo completo se re-ejecuta (bug del 'estado entregado' pegado)."""
    cli = await factoria.cliente()
    veh = await factoria.vehiculo()
    cond = await factoria.conductor()
    orden = await factoria.orden(cli.id)
    asg_id = (await _asignar(client, orden.id, cond.id, veh.placa)).json()["id"]

    # Run completado directamente en BD (entregar vía API exige multipart + GridFS).
    destino = (await db.execute(select(Destino).where(Destino.orden_id == orden.id))).scalar_one()
    asignacion = await db.get(Asignacion, asg_id)
    destino.estado = "Entregado"
    destino.entrega_receptor = "Receptor X"
    orden.estado = "Entregado"
    asignacion.estado = "Finalizada"
    cond.disponibilidad = "Disponible"
    await db.commit()

    # Sin flag: nada que reabrir (todos entregados) → 400 accionable.
    r = await client.patch(f"/api/asignaciones/{asg_id}/reabrir")
    assert r.status_code == 400
    assert "entregados" in r.json()["detail"]

    # Con flag: el destino se resetea y el conductor puede volver a entregar.
    r = await client.patch(f"/api/asignaciones/{asg_id}/reabrir", json={"reabrir_entregados": True})
    assert r.status_code == 200, r.text
    await db.refresh(destino)
    await db.refresh(orden)
    await db.refresh(cond)
    assert destino.estado == "Pendiente"
    assert destino.entrega_receptor is None
    assert orden.estado == "En Tránsito"
    assert cond.disponibilidad == "Ocupado"


async def test_eliminar_asignacion_revierte_orden_y_conductor(client, factoria, db):
    cli = await factoria.cliente()
    veh = await factoria.vehiculo()
    cond = await factoria.conductor()
    orden = await factoria.orden(cli.id)
    asg_id = (await _asignar(client, orden.id, cond.id, veh.placa)).json()["id"]

    r = await client.delete(f"/api/asignaciones/{asg_id}")
    assert r.status_code == 204, r.text

    await db.refresh(orden)
    await db.refresh(cond)
    assert orden.estado == "Pendiente"  # vuelve a la cola de despacho
    assert cond.disponibilidad == "Disponible"
