from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, distinct, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.dependencies import get_mongo_db, require_permiso
from core.config import settings
from core.database import get_db
from models.asignaciones import Asignacion
from models.calificaciones import Calificacion
from models.clientes import Cliente
from models.conductores import Conductor
from models.incidencias import Incidencia
from models.ordenes import Factura, Orden, Pago
from models.usuarios import Usuario
from models.vehiculos import Vehiculo
from services.mongo import (
    evidencias_service,
    geocerca_service,
    notificaciones_service,
    tracking_service,
)

router = APIRouter(prefix="/reportes", tags=["reportes"])


@router.get("/dashboard")
async def dashboard(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("reportes", "read")),
) -> dict[str, Any]:
    """KPIs generales: counts por entidad + ordenes por estado + recaudacion ultimas 24h."""
    ultimas_24h = datetime.now(timezone.utc) - timedelta(hours=24)

    total_clientes = (await db.execute(select(func.count(Cliente.id)).where(Cliente.activo == True))).scalar() or 0
    total_usuarios = (await db.execute(select(func.count(Usuario.id)).where(Usuario.activo == True))).scalar() or 0
    total_conductores = (await db.execute(select(func.count(Conductor.id)).where(Conductor.activo == True))).scalar() or 0
    total_vehiculos = (await db.execute(select(func.count(Vehiculo.placa)).where(Vehiculo.activo == True))).scalar() or 0
    total_ordenes = (await db.execute(select(func.count(Orden.id)))).scalar() or 0
    total_asignaciones = (await db.execute(select(func.count(Asignacion.id)))).scalar() or 0

    ordenes_por_estado_rows = (
        await db.execute(select(Orden.estado, func.count(Orden.id)).group_by(Orden.estado))
    ).all()
    ordenes_por_estado = {estado: n for estado, n in ordenes_por_estado_rows}

    conductores_disp_rows = (
        await db.execute(
            select(Conductor.disponibilidad, func.count(Conductor.id))
            .where(Conductor.activo == True)
            .group_by(Conductor.disponibilidad)
        )
    ).all()
    conductores_por_disp = {d: n for d, n in conductores_disp_rows}

    vehiculos_estado_rows = (
        await db.execute(
            select(Vehiculo.estado, func.count(Vehiculo.placa))
            .where(Vehiculo.activo == True)
            .group_by(Vehiculo.estado)
        )
    ).all()
    vehiculos_por_estado = {e: n for e, n in vehiculos_estado_rows}

    recaudacion_24h = (
        await db.execute(
            select(func.coalesce(func.sum(Pago.monto), 0))
            .where(Pago.estado == "Pagado", Pago.fecha_pago >= ultimas_24h)
        )
    ).scalar() or Decimal("0")

    incidencias_abiertas = (
        await db.execute(select(func.count(Incidencia.id)).where(Incidencia.severidad >= 3))
    ).scalar() or 0

    # Órdenes retenidas por pago desde hace más de PAGO_AVISO_DIAS: no se auto-cancelan
    # (decisión de negocio), pero se resaltan para que el staff decida (cobrar/cancelar).
    umbral_impagas = datetime.now(timezone.utc) - timedelta(days=settings.PAGO_AVISO_DIAS)
    impagas_antiguas = (
        await db.execute(
            select(func.count(Orden.id)).where(
                Orden.estado == "Pendiente de Pago", Orden.fecha_creacion < umbral_impagas
            )
        )
    ).scalar() or 0

    return {
        "totales": {
            "clientes": total_clientes,
            "usuarios": total_usuarios,
            "conductores": total_conductores,
            "vehiculos": total_vehiculos,
            "ordenes": total_ordenes,
            "asignaciones": total_asignaciones,
        },
        "ordenes_por_estado": ordenes_por_estado,
        "conductores_por_disponibilidad": conductores_por_disp,
        "vehiculos_por_estado": vehiculos_por_estado,
        "recaudacion_ultimas_24h": float(recaudacion_24h),
        "incidencias_severidad_alta": incidencias_abiertas,
        "ordenes_impagas_antiguas": impagas_antiguas,
        "pago_aviso_dias": settings.PAGO_AVISO_DIAS,
    }


@router.get("/ventas")
async def reporte_ventas(
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    granularidad: str = Query("dia", pattern="^(dia|mes)$"),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("reportes", "read")),
) -> dict[str, Any]:
    """Recaudacion agregada por dia o mes. Por defecto: ultimos 30 dias (dia) o 12 meses (mes)."""
    if hasta is None:
        hasta = datetime.now(timezone.utc)
    if desde is None:
        desde = hasta - timedelta(days=365 if granularidad == "mes" else 30)

    if granularidad == "mes":
        bucket = func.date_trunc("month", Pago.fecha_pago).label("periodo")
    else:
        bucket = func.date_trunc("day", Pago.fecha_pago).label("periodo")

    stmt = (
        select(
            bucket,
            func.count(Pago.id).label("pagos"),
            func.coalesce(func.sum(Pago.monto), 0).label("total"),
        )
        .where(Pago.estado == "Pagado", Pago.fecha_pago >= desde, Pago.fecha_pago <= hasta)
        .group_by(bucket)
        .order_by(bucket)
    )
    rows = (await db.execute(stmt)).all()

    total_general = sum((Decimal(str(r.total)) for r in rows), Decimal("0"))
    facturado = (
        await db.execute(
            select(func.coalesce(func.sum(Factura.monto), 0))
            .where(Factura.fecha >= desde, Factura.fecha <= hasta)
        )
    ).scalar() or Decimal("0")

    return {
        "desde": desde,
        "hasta": hasta,
        "granularidad": granularidad,
        "series": [
            {"periodo": r.periodo, "pagos": r.pagos, "monto": float(r.total)} for r in rows
        ],
        "total_recaudado": float(total_general),
        "total_facturado": float(facturado),
    }


@router.get("/top-clientes")
async def top_clientes(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("reportes", "read")),
) -> list[dict[str, Any]]:
    """Top clientes por monto recaudado en pagos confirmados."""
    stmt = (
        select(
            Cliente.id,
            Cliente.nombre,
            Cliente.email,
            func.count(distinct(Orden.id)).label("ordenes"),
            func.coalesce(func.sum(Pago.monto), 0).label("recaudado"),
        )
        .join(Orden, Orden.cliente_id == Cliente.id)
        .outerjoin(Pago, (Pago.orden_id == Orden.id) & (Pago.estado == "Pagado"))
        .group_by(Cliente.id, Cliente.nombre, Cliente.email)
        .order_by(func.coalesce(func.sum(Pago.monto), 0).desc())
        .limit(limit)
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "cliente_id": r.id,
            "nombre": r.nombre,
            "email": r.email,
            "ordenes": r.ordenes,
            "recaudado": float(r.recaudado),
        }
        for r in rows
    ]


@router.get("/conductores")
async def reporte_conductores(
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("reportes", "read")),
) -> list[dict[str, Any]]:
    """Metricas por conductor: asignaciones totales, finalizadas, incidencias."""
    stmt = (
        select(
            Conductor.id,
            Conductor.nombre,
            Conductor.disponibilidad,
            Conductor.vehiculo_placa,
            func.count(distinct(Asignacion.id)).label("total_asignaciones"),
            func.sum(case((Asignacion.estado == "Finalizada", 1), else_=0)).label("finalizadas"),
            func.sum(case((Asignacion.estado == "EnCurso", 1), else_=0)).label("en_curso"),
            func.count(distinct(Incidencia.id)).label("incidencias"),
            func.avg(Calificacion.puntaje).label("rating"),
            func.count(distinct(Calificacion.id)).label("total_calificaciones"),
        )
        .outerjoin(Asignacion, Asignacion.conductor_id == Conductor.id)
        .outerjoin(Incidencia, Incidencia.asignacion_id == Asignacion.id)
        .outerjoin(Calificacion, Calificacion.conductor_id == Conductor.id)
        .where(Conductor.activo == True)
        .group_by(Conductor.id, Conductor.nombre, Conductor.disponibilidad, Conductor.vehiculo_placa)
        .order_by(func.count(distinct(Asignacion.id)).desc())
    )
    rows = (await db.execute(stmt)).all()
    return [
        {
            "conductor_id": r.id,
            "nombre": r.nombre,
            "disponibilidad": r.disponibilidad,
            "vehiculo_placa": r.vehiculo_placa,
            "total_asignaciones": r.total_asignaciones,
            "finalizadas": int(r.finalizadas or 0),
            "en_curso": int(r.en_curso or 0),
            "incidencias": r.incidencias,
            "rating": round(float(r.rating), 2) if r.rating is not None else None,
            "total_calificaciones": int(r.total_calificaciones or 0),
        }
        for r in rows
    ]


@router.get("/incidencias")
async def reporte_incidencias(
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("reportes", "read")),
) -> dict[str, Any]:
    """Resumen de incidencias por severidad y tipo, en una ventana opcional."""
    stmt_sev = select(Incidencia.severidad, func.count(Incidencia.id)).group_by(Incidencia.severidad)
    stmt_tipo = (
        select(Incidencia.tipo, func.count(Incidencia.id))
        .group_by(Incidencia.tipo)
        .order_by(func.count(Incidencia.id).desc())
    )
    if desde is not None:
        stmt_sev = stmt_sev.where(Incidencia.fecha >= desde)
        stmt_tipo = stmt_tipo.where(Incidencia.fecha >= desde)
    if hasta is not None:
        stmt_sev = stmt_sev.where(Incidencia.fecha <= hasta)
        stmt_tipo = stmt_tipo.where(Incidencia.fecha <= hasta)

    sev_rows = (await db.execute(stmt_sev)).all()
    tipo_rows = (await db.execute(stmt_tipo)).all()
    total = sum(n for _, n in sev_rows)

    return {
        "desde": desde,
        "hasta": hasta,
        "total": total,
        "por_severidad": {int(s): n for s, n in sev_rows},
        "por_tipo": [{"tipo": t, "count": n} for t, n in tipo_rows],
    }


@router.get("/tiempos-entrega")
async def reporte_tiempos_entrega(
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("reportes", "read")),
) -> dict[str, Any]:
    """Tiempo promedio, min y max entre fecha_inicio y fecha_fin de asignaciones finalizadas (segundos)."""
    duracion = func.extract("epoch", Asignacion.fecha_fin - Asignacion.fecha_inicio)
    stmt = (
        select(
            func.count(Asignacion.id).label("n"),
            func.avg(duracion).label("avg_s"),
            func.min(duracion).label("min_s"),
            func.max(duracion).label("max_s"),
        )
        .where(Asignacion.estado == "Finalizada", Asignacion.fecha_inicio.isnot(None), Asignacion.fecha_fin.isnot(None))
    )
    if desde is not None:
        stmt = stmt.where(Asignacion.fecha_fin >= desde)
    if hasta is not None:
        stmt = stmt.where(Asignacion.fecha_fin <= hasta)
    row = (await db.execute(stmt)).one()

    def _fmt(s):
        return float(s) if s is not None else None

    return {
        "desde": desde,
        "hasta": hasta,
        "asignaciones_finalizadas": row.n or 0,
        "tiempo_promedio_segundos": _fmt(row.avg_s),
        "tiempo_minimo_segundos": _fmt(row.min_s),
        "tiempo_maximo_segundos": _fmt(row.max_s),
        "tiempo_promedio_minutos": _fmt(row.avg_s / 60) if row.avg_s else None,
    }


@router.get("/cliente/{cliente_id}/resumen")
async def resumen_cliente(
    cliente_id: int,
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("reportes", "read")),
) -> dict[str, Any]:
    """Vista 360 de un cliente: ordenes, pagos, facturas, estado."""
    cliente = await db.get(Cliente, cliente_id)
    if cliente is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Cliente no encontrado")

    total_ordenes = (await db.execute(select(func.count(Orden.id)).where(Orden.cliente_id == cliente_id))).scalar() or 0
    por_estado = dict(
        (await db.execute(
            select(Orden.estado, func.count(Orden.id))
            .where(Orden.cliente_id == cliente_id)
            .group_by(Orden.estado)
        )).all()
    )
    recaudado = (
        await db.execute(
            select(func.coalesce(func.sum(Pago.monto), 0))
            .join(Orden, Orden.id == Pago.orden_id)
            .where(Orden.cliente_id == cliente_id, Pago.estado == "Pagado")
        )
    ).scalar() or Decimal("0")
    facturado = (
        await db.execute(
            select(func.coalesce(func.sum(Factura.monto), 0))
            .join(Orden, Orden.id == Factura.orden_id)
            .where(Orden.cliente_id == cliente_id)
        )
    ).scalar() or Decimal("0")

    return {
        "cliente": {"id": cliente.id, "nombre": cliente.nombre, "email": cliente.email, "activo": cliente.activo},
        "total_ordenes": total_ordenes,
        "ordenes_por_estado": por_estado,
        "total_recaudado": float(recaudado),
        "total_facturado": float(facturado),
    }


@router.get("/operativo")
async def reporte_operativo(
    ventana_minutos: int = Query(5, ge=1, le=60, description="Ventana para considerar un conductor 'online'"),
    db: AsyncSession = Depends(get_db),
    mongo_db=Depends(get_mongo_db),
    _: object = Depends(require_permiso("reportes", "read")),
) -> dict[str, Any]:
    """KPIs operativos cruzando Postgres (asignaciones/conductores) y Mongo (tracking/geocercas)."""
    asignaciones_activas = (
        await db.execute(
            select(func.count(Asignacion.id)).where(Asignacion.estado == "EnCurso")
        )
    ).scalar() or 0

    conductores_ocupados = (
        await db.execute(
            select(func.count(Conductor.id)).where(
                Conductor.activo == True, Conductor.disponibilidad == "Ocupado"
            )
        )
    ).scalar() or 0

    desde = datetime.now(timezone.utc) - timedelta(minutes=ventana_minutos)
    tracking_coll = mongo_db[tracking_service.COLLECTION]
    online_pipeline = [
        {"$match": {"timestamp": {"$gte": desde}}},
        {"$group": {"_id": "$conductor_id"}},
        {"$count": "n"},
    ]
    online_rows = [d async for d in tracking_coll.aggregate(online_pipeline)]
    conductores_online = online_rows[0]["n"] if online_rows else 0

    asign_activas_ids = [
        row[0]
        for row in (
            await db.execute(
                select(Asignacion.id).where(Asignacion.estado == "EnCurso")
            )
        ).all()
    ]
    sin_tracking = 0
    if asign_activas_ids:
        con_tracking_pipeline = [
            {"$match": {"asignacion_id": {"$in": asign_activas_ids}, "timestamp": {"$gte": desde}}},
            {"$group": {"_id": "$asignacion_id"}},
        ]
        con_tracking = {d["_id"] async for d in tracking_coll.aggregate(con_tracking_pipeline)}
        sin_tracking = len(asign_activas_ids) - len(con_tracking)

    inicio_dia = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    km_pipeline = [
        {"$match": {"timestamp": {"$gte": inicio_dia}}},
        {"$sort": {"asignacion_id": 1, "timestamp": 1}},
        {
            "$group": {
                "_id": "$asignacion_id",
                "pings": {"$sum": 1},
            }
        },
        {"$count": "asignaciones_con_ping_hoy"},
    ]
    km_rows = [d async for d in tracking_coll.aggregate(km_pipeline)]
    asignaciones_con_ping_hoy = km_rows[0]["asignaciones_con_ping_hoy"] if km_rows else 0

    geocercas_activas = await mongo_db[geocerca_service.COLLECTION].count_documents({"activa": True})

    incidencias_24h = (
        await db.execute(
            select(func.count(Incidencia.id)).where(
                Incidencia.fecha >= datetime.now(timezone.utc) - timedelta(hours=24)
            )
        )
    ).scalar() or 0

    return {
        "ventana_minutos": ventana_minutos,
        "asignaciones_en_curso": asignaciones_activas,
        "conductores_ocupados_postgres": conductores_ocupados,
        "conductores_online_mongo": conductores_online,
        "asignaciones_activas_sin_tracking": sin_tracking,
        "asignaciones_con_ping_hoy": asignaciones_con_ping_hoy,
        "geocercas_activas": geocercas_activas,
        "incidencias_ultimas_24h": incidencias_24h,
    }


@router.get("/asignacion/{asignacion_id}/completo")
async def resumen_asignacion(
    asignacion_id: int,
    db: AsyncSession = Depends(get_db),
    mongo_db=Depends(get_mongo_db),
    _: object = Depends(require_permiso("reportes", "read")),
) -> dict[str, Any]:
    """Vista 360 cruzando Postgres (asignacion + incidencias) y Mongo (tracking + evidencias + notificaciones)."""
    from fastapi import HTTPException

    asignacion = await db.get(Asignacion, asignacion_id)
    if asignacion is None:
        raise HTTPException(status_code=404, detail="Asignacion no encontrada")

    incidencias_rows = (
        await db.execute(
            select(Incidencia.severidad, func.count(Incidencia.id))
            .where(Incidencia.asignacion_id == asignacion_id)
            .group_by(Incidencia.severidad)
        )
    ).all()
    incidencias_por_severidad = {int(s): n for s, n in incidencias_rows}
    incidencias_total = sum(incidencias_por_severidad.values())

    tracking_stats = await tracking_service.estadisticas_asignacion(mongo_db, asignacion_id)

    incidencias_ids = [
        row[0]
        for row in (
            await db.execute(
                select(Incidencia.id).where(Incidencia.asignacion_id == asignacion_id)
            )
        ).all()
    ]
    evidencias_total = 0
    evidencias_por_tipo: dict[str, int] = {}
    if incidencias_ids:
        ev_pipeline = [
            {"$match": {"incidencia_id": {"$in": incidencias_ids}}},
            {"$group": {"_id": "$tipo", "n": {"$sum": 1}}},
        ]
        async for d in mongo_db[evidencias_service.COLLECTION].aggregate(ev_pipeline):
            evidencias_por_tipo[d["_id"]] = d["n"]
            evidencias_total += d["n"]

    conductor = await db.get(Conductor, asignacion.conductor_id)
    notificaciones_conductor = await mongo_db[notificaciones_service.COLLECTION].count_documents(
        {"destinatario_tipo": "usuario", "destinatario_id": conductor.usuario_id}
    )

    return {
        "asignacion": {
            "id": asignacion.id,
            "estado": asignacion.estado,
            "conductor_id": asignacion.conductor_id,
            "vehiculo_placa": asignacion.vehiculo_placa,
            "orden_id": asignacion.orden_id,
            "fecha_inicio": asignacion.fecha_inicio,
            "fecha_fin": asignacion.fecha_fin,
        },
        "incidencias": {
            "total": incidencias_total,
            "por_severidad": incidencias_por_severidad,
        },
        "tracking": tracking_stats,
        "evidencias": {
            "total": evidencias_total,
            "por_tipo": evidencias_por_tipo,
        },
        "notificaciones_al_conductor": notificaciones_conductor,
    }


@router.get("/evidencias")
async def reporte_evidencias(
    mongo_db=Depends(get_mongo_db),
    _: object = Depends(require_permiso("reportes", "read")),
) -> dict[str, Any]:
    """KPIs de evidencias: por tipo, espacio en GridFS y top incidencias."""
    coll = mongo_db[evidencias_service.COLLECTION]

    total = await coll.count_documents({})

    por_tipo_pipeline = [{"$group": {"_id": "$tipo", "n": {"$sum": 1}}}]
    por_tipo = {d["_id"]: d["n"] async for d in coll.aggregate(por_tipo_pipeline)}

    espacio_pipeline = [
        {"$unwind": {"path": "$archivos", "preserveNullAndEmptyArrays": False}},
        {
            "$group": {
                "_id": None,
                "archivos": {"$sum": 1},
                "bytes": {"$sum": "$archivos.size"},
            }
        },
    ]
    espacio_rows = [d async for d in coll.aggregate(espacio_pipeline)]
    if espacio_rows:
        archivos_total = espacio_rows[0]["archivos"]
        bytes_total = espacio_rows[0]["bytes"] or 0
    else:
        archivos_total = 0
        bytes_total = 0

    top_pipeline = [
        {"$group": {"_id": "$incidencia_id", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}},
        {"$limit": 10},
    ]
    top_incidencias = [
        {"incidencia_id": d["_id"], "evidencias": d["n"]} async for d in coll.aggregate(top_pipeline)
    ]

    return {
        "total_evidencias": total,
        "por_tipo": por_tipo,
        "archivos_en_gridfs": archivos_total,
        "bytes_totales": bytes_total,
        "megabytes_totales": round(bytes_total / (1024 * 1024), 2),
        "top_incidencias_con_evidencias": top_incidencias,
    }


@router.get("/notificaciones")
async def reporte_notificaciones(
    horas: int = Query(24, ge=1, le=720),
    mongo_db=Depends(get_mongo_db),
    _: object = Depends(require_permiso("reportes", "read")),
) -> dict[str, Any]:
    """Resumen de notificaciones en una ventana: por tipo destinatario, leidas vs pendientes."""
    desde = datetime.now(timezone.utc) - timedelta(hours=horas)
    coll = mongo_db[notificaciones_service.COLLECTION]
    base = {"fecha": {"$gte": desde}}

    total = await coll.count_documents(base)
    leidas = await coll.count_documents({**base, "leida": True})
    pendientes = total - leidas

    por_dest_pipeline = [
        {"$match": base},
        {
            "$group": {
                "_id": "$destinatario_tipo",
                "n": {"$sum": 1},
                "leidas": {"$sum": {"$cond": ["$leida", 1, 0]}},
            }
        },
    ]
    por_destinatario = [
        {"tipo": d["_id"], "total": d["n"], "leidas": d["leidas"], "pendientes": d["n"] - d["leidas"]}
        async for d in coll.aggregate(por_dest_pipeline)
    ]

    return {
        "ventana_horas": horas,
        "desde": desde,
        "total": total,
        "leidas": leidas,
        "pendientes": pendientes,
        "por_destinatario": por_destinatario,
    }


@router.get("/sla-entregas")
async def reporte_sla_entregas(
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    sla_minutos: int = Query(60, ge=1, le=24 * 60),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("reportes", "read")),
) -> dict[str, Any]:
    """% de asignaciones finalizadas dentro del SLA configurable + percentiles de duracion."""
    duracion_s = func.extract("epoch", Asignacion.fecha_fin - Asignacion.fecha_inicio)
    sla_s = sla_minutos * 60

    base_filter = [
        Asignacion.estado == "Finalizada",
        Asignacion.fecha_inicio.isnot(None),
        Asignacion.fecha_fin.isnot(None),
    ]
    if desde is not None:
        base_filter.append(Asignacion.fecha_fin >= desde)
    if hasta is not None:
        base_filter.append(Asignacion.fecha_fin <= hasta)

    stmt = select(
        func.count(Asignacion.id).label("total"),
        func.sum(case((duracion_s <= sla_s, 1), else_=0)).label("on_time"),
        func.percentile_cont(0.5).within_group(duracion_s).label("p50_s"),
        func.percentile_cont(0.95).within_group(duracion_s).label("p95_s"),
    ).where(*base_filter)

    row = (await db.execute(stmt)).one()
    total = int(row.total or 0)
    on_time = int(row.on_time or 0)
    off_time = total - on_time
    pct = (on_time / total * 100.0) if total else None

    def _to_min(s):
        return round(float(s) / 60.0, 2) if s is not None else None

    return {
        "desde": desde,
        "hasta": hasta,
        "sla_minutos": sla_minutos,
        "total_entregas": total,
        "on_time": on_time,
        "off_time": off_time,
        "on_time_pct": round(pct, 2) if pct is not None else None,
        "p50_minutos": _to_min(row.p50_s),
        "p95_minutos": _to_min(row.p95_s),
    }


@router.get("/conductores/eficiencia")
async def reporte_conductores_eficiencia(
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    limit: int = Query(20, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("reportes", "read")),
) -> list[dict[str, Any]]:
    """Por conductor activo: entregas finalizadas, horas activas, entregas/hora y tasa de incidencias."""
    duracion_h = func.extract("epoch", Asignacion.fecha_fin - Asignacion.fecha_inicio) / 3600.0

    finalizadas_pred = case(
        (
            (Asignacion.estado == "Finalizada")
            & Asignacion.fecha_inicio.isnot(None)
            & Asignacion.fecha_fin.isnot(None),
            1,
        ),
        else_=0,
    )
    horas_pred = case(
        (
            (Asignacion.estado == "Finalizada")
            & Asignacion.fecha_inicio.isnot(None)
            & Asignacion.fecha_fin.isnot(None),
            duracion_h,
        ),
        else_=0,
    )

    asignacion_filters = []
    if desde is not None:
        asignacion_filters.append(Asignacion.fecha_fin >= desde)
    if hasta is not None:
        asignacion_filters.append(Asignacion.fecha_fin <= hasta)

    asignacion_join_cond = Asignacion.conductor_id == Conductor.id
    if asignacion_filters:
        from sqlalchemy import and_

        asignacion_join_cond = and_(asignacion_join_cond, *asignacion_filters)

    stmt = (
        select(
            Conductor.id,
            Conductor.nombre,
            func.coalesce(func.sum(finalizadas_pred), 0).label("entregas"),
            func.coalesce(func.sum(horas_pred), 0).label("horas_activas"),
            func.count(distinct(Incidencia.id)).label("incidencias"),
            func.sum(case((Incidencia.severidad >= 3, 1), else_=0)).label("incidencias_severas"),
        )
        .outerjoin(Asignacion, asignacion_join_cond)
        .outerjoin(Incidencia, Incidencia.asignacion_id == Asignacion.id)
        .where(Conductor.activo == True)
        .group_by(Conductor.id, Conductor.nombre)
        .order_by(
            (
                func.coalesce(func.sum(finalizadas_pred), 0)
                / func.nullif(func.coalesce(func.sum(horas_pred), 0), 0)
            ).desc().nullslast()
        )
        .limit(limit)
    )

    rows = (await db.execute(stmt)).all()
    out: list[dict[str, Any]] = []
    for r in rows:
        entregas = int(r.entregas or 0)
        horas = float(r.horas_activas or 0)
        incidencias = int(r.incidencias or 0)
        out.append(
            {
                "conductor_id": r.id,
                "nombre": r.nombre,
                "entregas_finalizadas": entregas,
                "horas_activas": round(horas, 2),
                "entregas_por_hora": round(entregas / horas, 2) if horas > 0 else None,
                "incidencias": incidencias,
                "incidencias_severas": int(r.incidencias_severas or 0),
                "tasa_incidencias": round(incidencias / entregas, 3) if entregas > 0 else None,
            }
        )
    return out


@router.get("/distribucion-geografica")
async def reporte_distribucion_geografica(
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    top: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("reportes", "read")),
) -> dict[str, Any]:
    """Top N distritos por volumen de ordenes (origen y destino) en el rango."""
    base_filter = []
    if desde is not None:
        base_filter.append(Orden.fecha_creacion >= desde)
    if hasta is not None:
        base_filter.append(Orden.fecha_creacion <= hasta)

    async def _top(columna):
        stmt = (
            select(columna.label("distrito"), func.count(Orden.id).label("n"))
            .where(columna.isnot(None), *base_filter)
            .group_by(columna)
            .order_by(func.count(Orden.id).desc())
            .limit(top)
        )
        rows = (await db.execute(stmt)).all()
        return [{"distrito": r.distrito, "ordenes": r.n} for r in rows]

    total = (
        await db.execute(select(func.count(Orden.id)).where(*base_filter))
    ).scalar() or 0

    return {
        "desde": desde,
        "hasta": hasta,
        "top": top,
        "total_ordenes": int(total),
        "top_origen": await _top(Orden.distrito_origen),
        "top_destino": await _top(Orden.distrito_destino),
    }
