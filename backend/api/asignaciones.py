from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.dependencies import (
    UserScope,
    get_current_user,
    get_mongo_db,
    get_scope,
    require_permiso,
)
from core.database import get_db
from core.estados import TRANSICIONES_ASIGNACION, validar_transicion
from core.pagination import ordenar, paginate
from core.realtime import CANAL_STAFF, canal_cliente, publish
from sqlalchemy.orm import selectinload

from models.asignaciones import Asignacion
from models.calificaciones import Calificacion
from models.conductores import Conductor
from models.destinos import Destino
from models.incidencias import Incidencia
from models.ordenes import Orden
from models.rutas import Parada
from models.usuarios import Usuario
from models.vehiculos import Vehiculo
from schemas.asignaciones import (
    AsignacionCreate,
    AsignacionResponse,
    AsignacionUpdate,
    EntregaOut,
    FinalizarAsignacionRequest,
    ReabrirAsignacionRequest,
    SugerenciaConductor,
)
from schemas.common import TipoEvidencia
from services.mongo import entregas_service, geocerca_service, tracking_service
from services.mongo.tracking_service import _haversine_m
from services import plaqueo_service, route_planner
from services.pricing_service import obtener_tarifa, peso_cobrable
from services.route_planner import generar_run

router = APIRouter(prefix="/asignaciones", tags=["asignaciones"])


def _solo_staff(scope: UserScope) -> None:
    if not scope.ve_todo():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acción reservada al personal interno")


def _asg_en_alcance(scope: UserScope, asignacion: Asignacion) -> bool:
    """El conductor solo opera SUS asignaciones; el staff todas."""
    if scope.ve_todo():
        return True
    if scope.conductor_id is not None:
        return asignacion.conductor_id == scope.conductor_id
    return False


def _dims_caben(paquete, caja) -> bool:
    """¿El paquete (l, a, h) cabe en la caja útil del vehículo (l, a, h)? Compara las
    dimensiones ORDENADAS (permite rotar el paquete). Si falta cualquier dimensión del
    paquete o del vehículo, se asume que cabe (no bloquea por dato faltante)."""
    if any(x is None for x in paquete) or any(x is None for x in caja):
        return True
    return all(float(p) <= float(c) for p, c in zip(sorted(paquete), sorted(caja)))


async def _peso_y_destinos(db: AsyncSession, orden_ids: list[int]):
    """Peso cobrable total (kg) de TODOS los destinos de las órdenes + la lista de destinos.
    Fuente única para la sugerencia y la validación de carga al asignar."""
    tarifa = await obtener_tarifa(db)
    destinos = (
        await db.execute(select(Destino).where(Destino.orden_id.in_(orden_ids)))
    ).scalars().all()
    peso_total = round(float(sum(
        peso_cobrable(
            tarifa,
            float(d.peso_kg) if d.peso_kg else None,
            float(d.largo_cm) if d.largo_cm else None,
            float(d.ancho_cm) if d.ancho_cm else None,
            float(d.alto_cm) if d.alto_cm else None,
        )
        for d in destinos
    )), 2)
    return peso_total, destinos


async def _peso_comprometido_vehiculo(db: AsyncSession, placa: str) -> float:
    """Peso (kg) ya comprometido en los runs ACTIVOS (Asignada/EnCurso) del vehículo:
    la carga de sus órdenes aún no terminales. Sin esto, varias asignaciones simultáneas
    podían sumar más carga que la capacidad real del vehículo."""
    activas = (
        await db.execute(
            select(Asignacion).where(
                Asignacion.vehiculo_placa == placa,
                Asignacion.estado.in_(("Asignada", "EnCurso")),
            )
        )
    ).scalars().all()
    orden_ids: list[int] = []
    for a in activas:
        orden_ids.extend(o.id for o in a.ordenes if o.estado not in ("Entregado", "Cancelado"))
    if not orden_ids:
        return 0.0
    peso, _ = await _peso_y_destinos(db, orden_ids)
    return peso


async def _validar_carga(db: AsyncSession, ordenes: list[Orden], vehiculo: Vehiculo) -> None:
    """Bloquea (409) si la carga (incluida la ya comprometida en runs activos del vehículo)
    supera su capacidad en kg, o si algún paquete no cabe en sus dimensiones útiles
    (cubicaje). Regla de negocio: no sobrecargar el vehículo."""
    peso_total, destinos = await _peso_y_destinos(db, [o.id for o in ordenes])
    cap = float(vehiculo.capacidad_kg) if vehiculo.capacidad_kg is not None else None
    if cap is not None:
        peso_previo = await _peso_comprometido_vehiculo(db, vehiculo.placa)
        if peso_total + peso_previo > cap:
            previo_txt = f" (ya lleva {peso_previo} kg en runs activos)" if peso_previo > 0 else ""
            raise HTTPException(
                status_code=409,
                detail=(
                    f"El vehículo {vehiculo.placa} no soporta la carga: se requieren {peso_total} kg"
                    f"{previo_txt} y su capacidad es {cap} kg. Elige un vehículo de mayor capacidad."
                ),
            )
    caja = (vehiculo.largo_cm, vehiculo.ancho_cm, vehiculo.alto_cm)
    for d in destinos:
        if not _dims_caben((d.largo_cm, d.ancho_cm, d.alto_cm), caja):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"El paquete del destino #{d.id} no cabe en las dimensiones útiles del vehículo "
                    f"{vehiculo.placa}. Elige un vehículo más grande."
                ),
            )


async def _avisar_estado_orden(db: AsyncSession, orden: Orden | None) -> None:
    """Publica el cambio de estado de la orden a su cliente y a la operación."""
    if orden is None:
        return
    evento = {"tipo": "orden", "accion": "estado", "orden_id": orden.id, "estado": orden.estado}
    await publish(canal_cliente(orden.cliente_id), evento)
    await publish(CANAL_STAFF, evento)


@router.get("/", response_model=list[AsignacionResponse])
async def list_asignaciones(
    response: Response,
    skip: int = 0,
    limit: int = Query(50, le=200),
    estado: str | None = None,
    conductor_id: int | None = None,
    q: str | None = Query(None, description="Busca por #orden o placa"),
    orden_por: str | None = Query(None, description="Campo de ordenamiento (cabecera)"),
    direccion: str | None = Query(None, alias="dir", description="asc | desc"),
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "read")),
):
    stmt = select(Asignacion)
    if not scope.ve_todo():
        # El conductor solo ve sus asignaciones; otros usuarios finales, ninguna.
        if scope.conductor_id is None:
            response.headers["X-Total-Count"] = "0"
            return []
        stmt = stmt.where(Asignacion.conductor_id == scope.conductor_id)
    elif conductor_id is not None:
        stmt = stmt.where(Asignacion.conductor_id == conductor_id)
    if estado is not None:
        stmt = stmt.where(Asignacion.estado == estado)
    if q:
        termino = q.strip().lstrip("#")
        condiciones = [Asignacion.vehiculo_placa.ilike(f"%{termino}%")]
        if termino.isdigit():
            condiciones.append(Asignacion.orden_id == int(termino))
            condiciones.append(Asignacion.id == int(termino))
        stmt = stmt.where(or_(*condiciones))
    stmt = ordenar(
        stmt, orden_por, direccion,
        {"id": Asignacion.id, "orden_id": Asignacion.orden_id, "estado": Asignacion.estado,
         "conductor_id": Asignacion.conductor_id, "vehiculo_placa": Asignacion.vehiculo_placa,
         "fecha_inicio": Asignacion.fecha_inicio},
        por_defecto=Asignacion.id.desc(),
    )
    # Body = lista simple; el total (sin paginar) viaja en el header X-Total-Count.
    return await paginate(db, stmt, response, skip, limit)


async def _asg_full(db: AsyncSession, asignacion_id: int) -> Asignacion | None:
    return (
        await db.execute(
            select(Asignacion).options(selectinload(Asignacion.ordenes)).where(Asignacion.id == asignacion_id)
        )
    ).scalar_one_or_none()


@router.post("/", response_model=AsignacionResponse, status_code=status.HTTP_201_CREATED)
async def create_asignacion(
    payload: AsignacionCreate,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    _solo_staff(scope)
    # Una o varias órdenes agrupadas en la misma ruta del conductor (la 1ª es la principal).
    ids: list[int] = list(dict.fromkeys(payload.orden_ids or ([payload.orden_id] if payload.orden_id else [])))
    if not ids:
        raise HTTPException(status_code=400, detail="Indica una o varias órdenes")

    # Lecturas con SELECT ... FOR UPDATE: dos dispatchers simultáneos no pueden asignar
    # el mismo conductor/orden/vehículo. El segundo espera el lock de fila y, al releer,
    # ve el estado ya cambiado ("Ocupado"/"En Proceso") y recibe el 400 correspondiente.
    # Los locks se liberan en el commit/rollback de esta misma transacción.
    ordenes: list[Orden] = []
    for oid in ids:
        orden = (
            await db.execute(select(Orden).where(Orden.id == oid).with_for_update())
        ).scalar_one_or_none()
        if orden is None:
            raise HTTPException(status_code=404, detail=f"Orden {oid} no encontrada")
        if orden.estado != "Pendiente":
            raise HTTPException(status_code=400, detail=f"Orden {oid} no está Pendiente (actual: {orden.estado})")
        ordenes.append(orden)

    conductor = (
        await db.execute(
            select(Conductor).where(Conductor.id == payload.conductor_id).with_for_update()
        )
    ).scalar_one_or_none()
    if conductor is None or not conductor.activo:
        raise HTTPException(status_code=400, detail="Conductor invalido o inactivo")
    if conductor.disponibilidad != "Disponible":
        raise HTTPException(status_code=400, detail=f"Conductor no disponible (actual: {conductor.disponibilidad})")

    vehiculo = (
        await db.execute(
            select(Vehiculo).where(Vehiculo.placa == payload.vehiculo_placa).with_for_update()
        )
    ).scalar_one_or_none()
    if vehiculo is None or not vehiculo.activo:
        raise HTTPException(status_code=400, detail="Vehiculo invalido o inactivo")
    if vehiculo.estado != "Operativo":
        raise HTTPException(status_code=400, detail=f"Vehiculo no operativo (actual: {vehiculo.estado})")

    # Capacidad y cubicaje: no se permite sobrecargar el vehículo (peso) ni asignar paquetes
    # que no caben físicamente (dimensiones). Bloquea con 409 si no cumple.
    await _validar_carga(db, ordenes, vehiculo)

    # Plaqueo (centro histórico de Arequipa). Si un recojo/entrega cae DENTRO de la zona en
    # un día restringido, es inevitable y se bloquea; si solo la ruta cruza la zona pero los
    # puntos están fuera, se permite y la ruta se reconstruye rebordeando el centro.
    plaqueo = await plaqueo_service.evaluar_asignacion(db, mongo_db, ordenes, payload.vehiculo_placa)
    if plaqueo["bloquear"]:
        b = plaqueo["bloquear"]
        raise HTTPException(
            status_code=409,
            detail=(
                f"Plaqueo: el vehículo {b['placa']} (placa termina en {b['digito']}) no puede "
                f"circular el {b['dia']} y la orden {b['orden_id']} recoge/entrega dentro del centro "
                "histórico. Elige otro vehículo o reprograma la entrega."
            ),
        )
    evitar_zonas = plaqueo["reroute"]

    primary = ordenes[0]
    # Si el plaqueo obliga a rebordear pero no existe una ruta que evite el centro, se
    # bloquea (no se asigna un vehículo a una ruta que cruzaría ilegalmente la zona).
    if evitar_zonas and not await route_planner.run_es_evitable(db, primary, ordenes, mongo_db):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Plaqueo: con el vehículo {payload.vehiculo_placa} no se pudo trazar una ruta que "
                "evite el centro histórico ese día. Elige otro vehículo o reprograma la entrega."
            ),
        )
    asignacion = Asignacion(
        orden_id=primary.id, conductor_id=payload.conductor_id,
        vehiculo_placa=payload.vehiculo_placa, estado="Asignada",
    )
    asignacion.ordenes = ordenes
    db.add(asignacion)
    for orden in ordenes:
        orden.estado = "En Proceso"
    conductor.disponibilidad = "Ocupado"
    await db.commit()

    # Construye una única ruta consolidada (recojos + entregas) optimizada; rebordea la
    # zona de restricción si el plaqueo lo requiere.
    try:
        await generar_run(db, primary, ordenes, mongo_db=mongo_db, evitar_zonas=evitar_zonas)
    except Exception as exc:  # noqa: BLE001 - la ruta es best-effort; la asignación YA está confirmada
        # El commit anterior persistió la asignación: este rollback solo descarta lo que
        # generar_run dejó a medias en la sesión (no "deshace" la asignación). El fallo se
        # registra como incidencia y se avisa al staff para que use "Regenerar ruta".
        await db.rollback()
        import logging
        logging.getLogger(__name__).warning("No se pudo generar la ruta del run %s: %s", asignacion.id, exc)
        db.add(Incidencia(
            asignacion_id=asignacion.id, tipo="Ruta no generada", severidad=2, origen="automatica",
            notas=f"No se pudo generar la ruta del run al asignar: {exc}. Regenérala desde la asignación.",
        ))
        await db.commit()
        await publish(CANAL_STAFF, {
            "tipo": "notificacion",
            "titulo": f"Asignación #{asignacion.id} sin ruta",
            "mensaje": "No se pudo generar la ruta del run. Regenérala desde Asignaciones.",
        })
    return await _asg_full(db, asignacion.id)


@router.post("/{asignacion_id}/regenerar-ruta", response_model=AsignacionResponse)
async def regenerar_ruta(
    asignacion_id: int,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    """(Re)genera la ruta consolidada del run — p. ej. si falló al crear la asignación
    (OSRM caído) o para recalcularla. `generar_run` reemplaza las rutas previas de las
    órdenes involucradas, así que es idempotente."""
    _solo_staff(scope)
    asignacion = await _asg_full(db, asignacion_id)
    if asignacion is None:
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    if asignacion.estado not in ("Asignada", "EnCurso"):
        raise HTTPException(
            status_code=400,
            detail=f"Solo se regenera la ruta de un run activo (actual: {asignacion.estado})",
        )
    ordenes = list(asignacion.ordenes)
    primary = next((o for o in ordenes if o.id == asignacion.orden_id), ordenes[0])
    # Mismo criterio de plaqueo que al asignar: rebordear el centro si la ruta lo cruza.
    plaqueo = await plaqueo_service.evaluar_asignacion(db, mongo_db, ordenes, asignacion.vehiculo_placa)
    try:
        await generar_run(db, primary, ordenes, mongo_db=mongo_db, evitar_zonas=plaqueo["reroute"])
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(status_code=502, detail=f"No se pudo generar la ruta: {exc}")
    return await _asg_full(db, asignacion_id)


@router.get("/sugerencia", response_model=list[SugerenciaConductor])
async def sugerir_conductor(
    orden_id: int | None = None,
    orden_ids: list[int] | None = Query(None),
    limit: int = Query(5, le=20),
    solo_aptos: bool = Query(False, description="Excluir candidatos restringidos o cuyo vehículo no soporta la carga"),
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "read")),
):
    """Sugiere los mejores conductores para una o varias órdenes a agrupar: disponibles,
    con vehículo operativo y CAPACIDAD suficiente, ordenados por capacidad suficiente,
    cercanía al origen (última posición GPS) y rating. Con `solo_aptos=true` excluye a los
    que no califican (plaqueo restringido, sin capacidad o donde el paquete no cabe)."""
    _solo_staff(scope)
    ids = list(dict.fromkeys(orden_ids or ([orden_id] if orden_id else [])))
    if not ids:
        raise HTTPException(status_code=400, detail="Indica una o varias órdenes")
    ordenes = []
    for oid in ids:
        o = await db.get(Orden, oid)
        if o is None:
            raise HTTPException(status_code=404, detail=f"Orden {oid} no encontrada")
        ordenes.append(o)

    # Peso requerido = suma del peso cobrable de todos los destinos de todas las órdenes.
    peso_total, destinos = await _peso_y_destinos(db, ids)

    rows = (
        await db.execute(
            select(Conductor, Vehiculo)
            .join(Vehiculo, Conductor.vehiculo_placa == Vehiculo.placa)
            .where(
                Conductor.activo.is_(True),
                Conductor.disponibilidad == "Disponible",
                Vehiculo.activo.is_(True),
                Vehiculo.estado == "Operativo",
            )
        )
    ).all()

    primary = ordenes[0]
    lon_o = float(primary.lon_origen) if primary.lon_origen is not None else None
    lat_o = float(primary.lat_origen) if primary.lat_origen is not None else None

    # Fechas de entrega cuya ruta cruza la zona de restricción (para evaluar plaqueo por placa).
    fechas_cruce = await plaqueo_service.fechas_con_cruce(db, mongo_db, ordenes)

    sugerencias: list[SugerenciaConductor] = []
    for cond, veh in rows:
        dist_km = None
        if lon_o is not None and lat_o is not None:
            pos = await tracking_service.ultima_posicion_conductor(mongo_db, cond.id)
            if pos:
                c = pos["location"]["coordinates"]
                dist_km = round(_haversine_m(c[0], c[1], lon_o, lat_o) / 1000.0, 2)
        prom, total = (
            await db.execute(
                select(func.avg(Calificacion.puntaje), func.count(Calificacion.id)).where(
                    Calificacion.conductor_id == cond.id
                )
            )
        ).one()
        cap = float(veh.capacidad_kg) if veh.capacidad_kg is not None else None
        suficiente = cap is None or peso_total == 0 or cap >= peso_total
        # Cubicaje: todos los paquetes deben caber en las dimensiones del vehículo.
        caja = (veh.largo_cm, veh.ancho_cm, veh.alto_cm)
        cabe = all(_dims_caben((d.largo_cm, d.ancho_cm, d.alto_cm), caja) for d in destinos)
        restringido = any(plaqueo_service.placa_restringida(cond.vehiculo_placa, f) for f in fechas_cruce)
        sugerencias.append(
            SugerenciaConductor(
                conductor_id=cond.id,
                nombre=cond.nombre,
                vehiculo_placa=cond.vehiculo_placa,
                distancia_km=dist_km,
                rating=round(float(prom), 2) if prom is not None else None,
                total_calificaciones=total or 0,
                capacidad_kg=cap,
                peso_requerido_kg=peso_total,
                suficiente=suficiente,
                cabe=cabe,
                restringido_plaqueo=restringido,
            )
        )

    if solo_aptos:
        sugerencias = [s for s in sugerencias if s.cabe and s.suficiente and not s.restringido_plaqueo]
    # No restringidos, que quepan y con capacidad primero; luego más cercano; sin posición al final; mejor rating.
    sugerencias.sort(key=lambda s: (s.restringido_plaqueo, not s.cabe, not s.suficiente, s.distancia_km is None, s.distancia_km or 0.0, -(s.rating or 0.0)))
    return sugerencias[:limit]


@router.get("/{asignacion_id}", response_model=AsignacionResponse)
async def get_asignacion(
    asignacion_id: int,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "read")),
):
    asignacion = await _asg_full(db, asignacion_id)
    if asignacion is None or not _asg_en_alcance(scope, asignacion):
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    return asignacion


async def _revertir_asignacion(db: AsyncSession, asignacion: Asignacion) -> None:
    """Devuelve las órdenes aún no iniciadas del run a 'Pendiente' (vuelven a la cola de
    despacho) y libera al conductor. Se usa al cancelar/eliminar una asignación que no
    llegó a iniciarse — sin esto quedaban órdenes 'En Proceso' y conductores 'Ocupado'
    fantasma. No hace commit (el llamador controla la transacción)."""
    for orden in asignacion.ordenes:
        if orden.estado == "En Proceso":
            orden.estado = "Pendiente"
    conductor = (
        await db.execute(
            select(Conductor).where(Conductor.id == asignacion.conductor_id).with_for_update()
        )
    ).scalar_one_or_none()
    if conductor is not None and conductor.disponibilidad == "Ocupado":
        conductor.disponibilidad = "Disponible"


@router.patch("/{asignacion_id}", response_model=AsignacionResponse)
async def update_asignacion(
    asignacion_id: int,
    payload: AsignacionUpdate,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    _solo_staff(scope)
    asignacion = await _asg_full(db, asignacion_id)
    if asignacion is None:
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    update = payload.model_dump(exclude_unset=True)
    # Cambios de estado a mano: solo transiciones legales (core/estados.py). Iniciar,
    # finalizar y reabrir tienen sus endpoints dedicados con guardas propias.
    nuevo_estado = update.pop("estado", None)
    ordenes_cambiadas: list[Orden] = []
    if nuevo_estado is not None and nuevo_estado != asignacion.estado:
        validar_transicion("asignación", asignacion.estado, nuevo_estado, TRANSICIONES_ASIGNACION)
        asignacion.estado = nuevo_estado
        if nuevo_estado == "Cancelada":
            asignacion.fecha_fin = datetime.now(timezone.utc)
            ordenes_cambiadas = [o for o in asignacion.ordenes if o.estado == "En Proceso"]
            await _revertir_asignacion(db, asignacion)
    for k, v in update.items():
        setattr(asignacion, k, v)
    await db.commit()
    for orden in ordenes_cambiadas:
        await _avisar_estado_orden(db, orden)
    return await _asg_full(db, asignacion_id)


@router.patch("/{asignacion_id}/iniciar", response_model=AsignacionResponse)
async def iniciar_asignacion(
    asignacion_id: int,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    asignacion = await _asg_full(db, asignacion_id)
    if asignacion is None or not _asg_en_alcance(scope, asignacion):
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    if asignacion.estado != "Asignada":
        raise HTTPException(status_code=400, detail=f"Asignacion no esta Asignada (actual: {asignacion.estado})")
    asignacion.estado = "EnCurso"
    asignacion.fecha_inicio = datetime.now(timezone.utc)
    # Todas las órdenes del run pasan a 'En Tránsito'.
    for orden in asignacion.ordenes:
        orden.estado = "En Tránsito"
    await db.commit()
    for orden in asignacion.ordenes:
        await _avisar_estado_orden(db, orden)
    return await _asg_full(db, asignacion_id)


async def _cerrar_completados(db: AsyncSession, asignacion: Asignacion, ahora) -> list[Orden]:
    """Cierra las órdenes cuyos destinos están todos en estado terminal (Entregado o
    Fallida): la orden queda 'Entregado' si al menos uno se entregó, o 'Cancelado' si
    ninguno. Si todo el run terminó, finaliza la asignación y libera al conductor.
    Devuelve las órdenes cuyo estado cambió (para avisar tras el commit)."""
    cambiadas: list[Orden] = []
    todos_terminales = True
    for orden in asignacion.ordenes:
        ds = (await db.execute(select(Destino).where(Destino.orden_id == orden.id))).scalars().all()
        terminales = [d for d in ds if d.estado in ("Entregado", "Fallida")]
        if len(terminales) < len(ds):
            todos_terminales = False
            continue
        if orden.estado in ("Entregado", "Cancelado"):
            continue
        orden.estado = "Entregado" if any(d.estado == "Entregado" for d in ds) else "Cancelado"
        cambiadas.append(orden)
    if todos_terminales and asignacion.estado == "EnCurso":
        asignacion.estado = "Finalizada"
        asignacion.fecha_fin = ahora
        conductor = await db.get(Conductor, asignacion.conductor_id)
        if conductor is not None:
            conductor.disponibilidad = "Disponible"
    return cambiadas


@router.patch("/{asignacion_id}/finalizar", response_model=AsignacionResponse)
async def finalizar_asignacion(
    asignacion_id: int,
    payload: FinalizarAsignacionRequest | None = None,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    """Cierre forzado por el staff (excepción): finaliza el run sin foto del conductor,
    exigiendo un motivo que queda registrado como incidencia para auditoría."""
    _solo_staff(scope)
    asignacion = await _asg_full(db, asignacion_id)
    if asignacion is None:
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    if asignacion.estado != "EnCurso":
        raise HTTPException(status_code=400, detail=f"Asignacion no esta EnCurso (actual: {asignacion.estado})")
    motivo = (payload.nota if payload else None) or ""
    if not motivo.strip():
        raise HTTPException(status_code=400, detail="Indica el motivo del cierre forzado")

    ahora = datetime.now(timezone.utc)
    receptor = (payload.receptor if payload else None) or "Cierre forzado"
    destinos = (
        await db.execute(select(Destino).where(Destino.orden_id.in_([o.id for o in asignacion.ordenes])))
    ).scalars().all()
    for d in destinos:
        if d.estado not in ("Entregado", "Fallida"):
            d.estado = "Entregado"
            d.entrega_receptor = receptor
            d.fecha_entrega = ahora
            d.nota = f"Cierre forzado: {motivo}"
            if payload and payload.lat is not None:
                d.entrega_lat = payload.lat
            if payload and payload.lon is not None:
                d.entrega_lon = payload.lon
            # Sincroniza la parada de la ruta planificada (igual que entregar/fallar destino).
            await _marcar_parada(db, d.id, ahora, "Visitada")
    asignacion.entrega_receptor = receptor
    # Registro de auditoría: incidencia del cierre forzado.
    db.add(Incidencia(asignacion_id=asignacion_id, tipo="Cierre forzado", severidad=2,
                      origen="admin", notas=motivo))
    cambiadas = await _cerrar_completados(db, asignacion, ahora)
    await db.commit()
    for orden in cambiadas:
        await _avisar_estado_orden(db, orden)
    return await _asg_full(db, asignacion_id)


@router.patch("/{asignacion_id}/reabrir", response_model=AsignacionResponse)
async def reabrir_asignacion(
    asignacion_id: int,
    payload: ReabrirAsignacionRequest | None = None,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    """Reapertura de un run cerrado por error: vuelve la asignación a 'EnCurso', sus órdenes
    a 'En Tránsito' y ocupa de nuevo al conductor.

    Por defecto solo se reabren los destinos 'Fallida' (reintento de los no entregados).
    Con `reabrir_entregados=true` también se resetean los 'Entregado' a 'Pendiente' —
    corrige cierres forzados o entregas marcadas por error, de modo que el CONDUCTOR
    vuelva a ver la entrega como pendiente y pueda re-ejecutar el flujo (la evidencia
    previa se conserva en el historial de la asignación)."""
    _solo_staff(scope)
    asignacion = await _asg_full(db, asignacion_id)
    if asignacion is None:
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    if asignacion.estado != "Finalizada":
        raise HTTPException(status_code=400, detail=f"Solo se reabre una asignacion Finalizada (actual: {asignacion.estado})")

    reabrir_entregados = bool(payload and payload.reabrir_entregados)
    estados_a_reabrir = ("Fallida", "Entregado") if reabrir_entregados else ("Fallida",)
    destinos = (
        await db.execute(select(Destino).where(Destino.orden_id.in_([o.id for o in asignacion.ordenes])))
    ).scalars().all()
    candidatos = [d for d in destinos if d.estado in estados_a_reabrir]
    if not candidatos:
        # Sin esto, un run 100% entregado se "reabría" dejando al conductor una lista
        # congelada en 'Entregado', sin nada que re-ejecutar (bug reportado).
        raise HTTPException(
            status_code=400,
            detail=(
                "No hay destinos que reabrir: todos están entregados. "
                "Activa «reabrir también los entregados» para reiniciar la entrega completa."
            ),
        )

    asignacion.estado = "EnCurso"
    asignacion.fecha_fin = None
    for d in candidatos:
        d.estado = "Pendiente"
        d.nota = None
        d.fecha_entrega = None
        d.entrega_receptor = None
        d.entrega_lat = None
        d.entrega_lon = None
        parada = (await db.execute(select(Parada).where(Parada.destino_id == d.id))).scalars().first()
        if parada is not None:
            parada.estado = "Pendiente"
            parada.fecha_paso = None
    cambiadas: list[Orden] = []
    for orden in asignacion.ordenes:
        if orden.estado in ("Entregado", "Cancelado"):
            orden.estado = "En Tránsito"
            cambiadas.append(orden)
    conductor = await db.get(Conductor, asignacion.conductor_id)
    if conductor is not None:
        conductor.disponibilidad = "Ocupado"
    await db.commit()
    for orden in cambiadas:
        await _avisar_estado_orden(db, orden)
    return await _asg_full(db, asignacion_id)


async def _validar_destino_en_curso(db, asignacion_id, destino_id, scope):
    asignacion = await _asg_full(db, asignacion_id)
    if asignacion is None or not _asg_en_alcance(scope, asignacion):
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    if asignacion.estado != "EnCurso":
        raise HTTPException(status_code=400, detail=f"Asignacion no esta EnCurso (actual: {asignacion.estado})")
    destino = await db.get(Destino, destino_id)
    if destino is None or destino.orden_id not in {o.id for o in asignacion.ordenes}:
        raise HTTPException(status_code=404, detail="Destino no pertenece a esta asignación")
    if destino.estado in ("Entregado", "Fallida"):
        raise HTTPException(status_code=400, detail=f"El destino ya está {destino.estado}")
    return asignacion, destino


async def _marcar_parada(db, destino_id, ahora, estado="Visitada"):
    parada = (await db.execute(select(Parada).where(Parada.destino_id == destino_id))).scalars().first()
    if parada is not None:
        parada.estado = estado
        parada.fecha_paso = ahora


@router.post("/{asignacion_id}/destinos/{destino_id}/entregar", response_model=EntregaOut, status_code=status.HTTP_201_CREATED)
async def entregar_destino(
    asignacion_id: int,
    destino_id: int,
    receptor: str = Form(...),
    lat: float | None = Form(None),
    lon: float | None = Form(None),
    archivos: list[UploadFile] = File(..., description="Foto/firma de la entrega de este destino"),
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    current_user: Usuario = Depends(get_current_user),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    """Entrega UN destino del run con evidencia obligatoria. Al quedar todos los destinos
    de una orden en estado terminal, la orden se cierra; al terminar el run, la asignación
    queda 'Finalizada'."""
    asignacion, destino = await _validar_destino_en_curso(db, asignacion_id, destino_id, scope)
    entrega = await entregas_service.crear_con_archivos(
        mongo_db, asignacion_id=asignacion_id, archivos=archivos, tipo="foto",
        descripcion=f"Entrega destino #{destino_id}", lat=lat, lon=lon, receptor=receptor,
        uploaded_by=current_user.id, destino_id=destino_id,
    )
    ahora = datetime.now(timezone.utc)
    destino.estado = "Entregado"
    destino.entrega_receptor = receptor
    destino.entrega_lat, destino.entrega_lon = lat, lon
    destino.fecha_entrega = ahora
    await _marcar_parada(db, destino_id, ahora, "Visitada")
    cambiadas = await _cerrar_completados(db, asignacion, ahora)
    await db.commit()
    for orden in cambiadas:
        await _avisar_estado_orden(db, orden)
    return entrega


@router.post("/{asignacion_id}/destinos/{destino_id}/fallar", response_model=AsignacionResponse)
async def fallar_destino(
    asignacion_id: int,
    destino_id: int,
    motivo: str = Form(...),
    lat: float | None = Form(None),
    lon: float | None = Form(None),
    archivos: list[UploadFile] = File(..., description="Evidencia obligatoria de la no entrega (foto de puerta cerrada, etc.)"),
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    current_user: Usuario = Depends(get_current_user),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    """Marca un destino como NO entregado (cliente ausente, dirección incorrecta…) con motivo
    y EVIDENCIA obligatoria. Crea una incidencia con la prueba y cierra la orden/run cuando ya
    no quedan destinos pendientes."""
    if not motivo.strip():
        raise HTTPException(status_code=400, detail="Indica el motivo de la no entrega")
    asignacion, destino = await _validar_destino_en_curso(db, asignacion_id, destino_id, scope)
    # Guarda la prueba visual de la no entrega (misma colección/GridFS que las entregas).
    await entregas_service.crear_con_archivos(
        mongo_db, asignacion_id=asignacion_id, archivos=archivos, tipo="foto",
        descripcion=f"No entrega destino #{destino_id}: {motivo.strip()}", lat=lat, lon=lon,
        receptor=None, uploaded_by=current_user.id, destino_id=destino_id,
    )
    ahora = datetime.now(timezone.utc)
    destino.estado = "Fallida"
    destino.nota = motivo.strip()
    destino.entrega_lat, destino.entrega_lon = lat, lon
    destino.fecha_entrega = ahora
    await _marcar_parada(db, destino_id, ahora, "Omitida")
    db.add(Incidencia(asignacion_id=asignacion_id, tipo="Entrega fallida", severidad=3,
                      origen="chofer", notas=motivo.strip()))
    cambiadas = await _cerrar_completados(db, asignacion, ahora)
    await db.commit()
    for orden in cambiadas:
        await _avisar_estado_orden(db, orden)
    return await _asg_full(db, asignacion_id)


@router.post(
    "/{asignacion_id}/prueba-entrega",
    response_model=EntregaOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_prueba_entrega(
    asignacion_id: int,
    tipo: TipoEvidencia = Form("foto"),
    descripcion: str | None = Form(None),
    receptor: str | None = Form(None),
    lat: float | None = Form(None),
    lon: float | None = Form(None),
    archivos: list[UploadFile] = File(..., description="Foto/firma de la entrega"),
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    current_user: Usuario = Depends(get_current_user),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "write")),
):
    """Sube la prueba de entrega (foto/firma) a GridFS y guarda coords/receptor en la asignacion."""
    asignacion = await db.get(Asignacion, asignacion_id)
    if asignacion is None or not _asg_en_alcance(scope, asignacion):
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    entrega = await entregas_service.crear_con_archivos(
        mongo_db,
        asignacion_id=asignacion_id,
        archivos=archivos,
        tipo=tipo,
        descripcion=descripcion,
        lat=lat,
        lon=lon,
        receptor=receptor,
        uploaded_by=current_user.id,
    )
    if lat is not None:
        asignacion.entrega_lat = lat
    if lon is not None:
        asignacion.entrega_lon = lon
    if receptor is not None:
        asignacion.entrega_receptor = receptor
    await db.commit()
    return entrega


@router.get("/{asignacion_id}/prueba-entrega", response_model=list[EntregaOut])
async def list_pruebas_entrega(
    asignacion_id: int,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("asignaciones", "read")),
):
    asignacion = await db.get(Asignacion, asignacion_id)
    if asignacion is None or not _asg_en_alcance(scope, asignacion):
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    return await entregas_service.listar_por_asignacion(mongo_db, asignacion_id)


@router.get("/prueba-entrega/archivos/{file_id}")
async def descargar_archivo_entrega(
    file_id: str,
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("asignaciones", "read")),
):
    grid_out = await entregas_service.abrir_descarga(mongo_db, file_id)
    if grid_out is None:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")

    metadata = grid_out.metadata or {}
    content_type = metadata.get("content_type") or "application/octet-stream"

    async def _iter():
        async for chunk in grid_out:
            yield chunk

    return StreamingResponse(
        _iter(),
        media_type=content_type,
        headers={
            "Content-Length": str(grid_out.length),
            "Content-Disposition": f'inline; filename="{grid_out.filename}"',
        },
    )


@router.delete("/{asignacion_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_asignacion(
    asignacion_id: int,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    _: object = Depends(require_permiso("asignaciones", "delete")),
):
    asignacion = await db.get(Asignacion, asignacion_id)
    if asignacion is None:
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")
    if asignacion.estado == "EnCurso":
        raise HTTPException(status_code=400, detail="No se puede borrar una asignacion en curso")
    # Borrar un run aún no iniciado no debe dejar huérfanos: órdenes de vuelta a la
    # cola ('Pendiente') y conductor 'Disponible'.
    if asignacion.estado == "Asignada":
        await _revertir_asignacion(db, asignacion)
    await tracking_service.eliminar_por_asignacion(mongo_db, asignacion_id)
    await geocerca_service.eliminar_por_asignacion(mongo_db, asignacion_id)
    await entregas_service.eliminar_por_asignacion(mongo_db, asignacion_id)
    await db.delete(asignacion)
    await db.commit()
