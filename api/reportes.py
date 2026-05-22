from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, distinct, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.dependencies import require_permiso
from core.database import get_db
from models.asignaciones import Asignacion
from models.clientes import Cliente
from models.conductores import Conductor
from models.incidencias import Incidencia
from models.ordenes import Factura, Orden, Pago
from models.usuarios import Usuario
from models.vehiculos import Vehiculo

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
    }


@router.get("/ventas")
async def reporte_ventas(
    desde: Optional[datetime] = None,
    hasta: Optional[datetime] = None,
    granularidad: str = Query("dia", regex="^(dia|mes)$"),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(require_permiso("reportes", "read")),
) -> dict[str, Any]:
    """Recaudacion agregada por dia o mes. Por defecto ultimos 30 dias."""
    if hasta is None:
        hasta = datetime.now(timezone.utc)
    if desde is None:
        desde = hasta - timedelta(days=30)

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
        )
        .outerjoin(Asignacion, Asignacion.conductor_id == Conductor.id)
        .outerjoin(Incidencia, Incidencia.asignacion_id == Asignacion.id)
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
