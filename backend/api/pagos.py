import logging
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from api.dependencies import UserScope, get_mongo_db, get_scope, orden_en_alcance, require_permiso
from core.config import settings
from core.database import get_db
from core.pagination import ordenar, paginate
from core.realtime import CANAL_STAFF, canal_cliente, publish
from models.ordenes import Orden, Pago
from schemas.mongo_notificaciones import NotificacionIn
from schemas.pagos import CheckoutResponse, PagoCreate, PagoResponse, PagoUpdate
from services.mongo import notificaciones_service
from services.payments import mercadopago

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pagos"])


async def _pago_pendiente(db: AsyncSession, orden: Orden) -> Pago:
    """Devuelve el pago pendiente de la orden (o crea uno por el total)."""
    pago = (
        await db.execute(
            select(Pago).where(Pago.orden_id == orden.id, Pago.estado == "Pendiente").order_by(Pago.id.desc())
        )
    ).scalars().first()
    if pago is None:
        pago = Pago(orden_id=orden.id, monto=orden.total, estado="Pendiente")
        db.add(pago)
        await db.flush()
    return pago


async def _confirmar_pago(db: AsyncSession, mongo_db, orden: Orden, pago: Pago, external_id: str, metodo: str) -> None:
    """Marca el pago como Pagado y, si la orden estaba 'Pendiente de Pago', la libera
    a 'Pendiente' (despachable). Notifica al cliente y a la operación."""
    pago.estado = "Pagado"
    pago.external_id = external_id
    pago.metodo = metodo
    pago.fecha_pago = datetime.now(timezone.utc)
    if orden.estado == "Pendiente de Pago":
        orden.estado = "Pendiente"
    await db.commit()

    await publish(canal_cliente(orden.cliente_id), {"tipo": "pago", "orden_id": orden.id, "estado": "Pagado"})
    await publish(CANAL_STAFF, {"tipo": "orden", "accion": "creada", "orden_id": orden.id, "estado": orden.estado})
    try:
        await notificaciones_service.crear(
            mongo_db,
            NotificacionIn(
                destinatario_tipo="cliente",
                destinatario_id=orden.cliente_id,
                tipo="pago",
                titulo="Pago confirmado",
                mensaje=f"Tu pago de la orden #{orden.id} fue confirmado. ¡Ya la estamos gestionando!",
            ),
        )
        await publish(canal_cliente(orden.cliente_id), {"tipo": "notificacion", "titulo": "Pago confirmado"})
    except Exception as exc:  # pragma: no cover - notificación best-effort
        logger.warning("No se pudo crear la notificación de pago: %s", exc)


@router.post("/ordenes/{orden_id}/checkout", response_model=CheckoutResponse)
async def checkout(
    orden_id: int,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("pagos", "write")),
):
    """Inicia el pago por adelantado de una orden 'Pendiente de Pago'. Devuelve la URL
    a la que redirigir al cliente (MercadoPago real o checkout simulado)."""
    orden = await db.get(Orden, orden_id)
    if orden is None or not await orden_en_alcance(db, scope, orden):
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    if orden.estado != "Pendiente de Pago":
        raise HTTPException(status_code=400, detail="La orden no está pendiente de pago")
    if orden.total is None or float(orden.total) <= 0:
        raise HTTPException(status_code=400, detail="La orden no tiene un monto válido")

    pago = await _pago_pendiente(db, orden)
    if settings.mp_enabled:
        try:
            pref = await mercadopago.crear_preferencia(orden.id, float(orden.total), f"Orden #{orden.id}")
        except Exception as exc:
            logger.error("Error creando preferencia MercadoPago: %s", exc)
            raise HTTPException(status_code=502, detail="No se pudo iniciar el pago con MercadoPago")
        pago.proveedor = "mercadopago"
        pago.preference_id = pref["preference_id"]
        await db.commit()
        return CheckoutResponse(
            orden_id=orden.id, init_point=pref["init_point"], preference_id=pref["preference_id"], proveedor="mercadopago"
        )

    # Modo simulado (sin llaves MP): el frontend mostrará una pantalla de pago simulado.
    pago.proveedor = "simulado"
    await db.commit()
    return CheckoutResponse(
        orden_id=orden.id,
        init_point=f"{settings.FRONTEND_BASE_URL}/pago/simulado?orden={orden.id}",
        proveedor="simulado",
    )


@router.post("/pagos/simular/{orden_id}", response_model=PagoResponse)
async def simular_pago(
    orden_id: int,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("pagos", "write")),
):
    """Confirma un pago en modo simulado (solo cuando MercadoPago no está configurado)."""
    if settings.mp_enabled:
        raise HTTPException(status_code=400, detail="MercadoPago está activo; usa la pasarela real")
    orden = await db.get(Orden, orden_id)
    if orden is None or not await orden_en_alcance(db, scope, orden):
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    if orden.estado != "Pendiente de Pago":
        raise HTTPException(status_code=400, detail="La orden no está pendiente de pago")
    pago = await _pago_pendiente(db, orden)
    await _confirmar_pago(db, mongo_db, orden, pago, external_id=f"SIM-{orden.id}", metodo="simulado")
    await db.refresh(pago)
    return pago


@router.post("/pagos/webhook/mercadopago")
async def webhook_mercadopago(
    request: Request,
    db: AsyncSession = Depends(get_db),
    mongo_db = Depends(get_mongo_db),
):
    """Webhook (público) de MercadoPago. Ante una notificación de pago, consulta el
    estado real en MP y, si está aprobado, confirma el pago de la orden. Siempre
    responde 200 para que MP no reintente en exceso."""
    tipo = request.query_params.get("type") or request.query_params.get("topic")
    payment_id = request.query_params.get("data.id") or request.query_params.get("id")
    if tipo is None or payment_id is None:
        try:
            body = await request.json()
            tipo = tipo or body.get("type")
            payment_id = payment_id or (body.get("data") or {}).get("id")
        except Exception:
            pass
    if tipo != "payment" or not payment_id:
        return {"received": True}

    try:
        info = await mercadopago.obtener_pago(str(payment_id))
    except Exception as exc:
        logger.warning("Webhook MP: no se pudo consultar el pago %s: %s", payment_id, exc)
        return {"received": True}

    if info.get("status") == "approved" and info.get("external_reference"):
        orden = await db.get(Orden, int(info["external_reference"]))
        if orden is not None:
            pago = await _pago_pendiente(db, orden)
            await _confirmar_pago(
                db, mongo_db, orden, pago, external_id=str(payment_id), metodo=info.get("payment_type_id") or "mercadopago"
            )
    return {"received": True}


@router.get("/pagos", response_model=list[PagoResponse])
async def list_pagos(
    response: Response,
    skip: int = 0,
    limit: int = Query(50, le=200),
    estado: str | None = None,
    proveedor: str | None = Query(None, description="Pasarela ('mercadopago', …) o 'manual' (staff)"),
    desde: datetime | None = None,
    hasta: datetime | None = None,
    q: str | None = Query(None, description="Busca por #orden o referencia bancaria"),
    orden_por: str | None = Query(None, description="Campo de ordenamiento (cabecera)"),
    direccion: str | None = Query(None, alias="dir", description="asc | desc"),
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("pagos", "read")),
):
    stmt = select(Pago)
    if not scope.ve_todo() and scope.cliente_id is not None:
        # El cliente solo ve los pagos de sus propias órdenes.
        stmt = stmt.where(Pago.orden_id.in_(select(Orden.id).where(Orden.cliente_id == scope.cliente_id)))
    if estado is not None:
        stmt = stmt.where(Pago.estado == estado)
    if proveedor is not None:
        # 'manual' = pagos registrados por el staff (sin pasarela → proveedor NULL).
        if proveedor == "manual":
            stmt = stmt.where(Pago.proveedor.is_(None))
        else:
            stmt = stmt.where(Pago.proveedor == proveedor)
    if desde is not None:
        stmt = stmt.where(Pago.fecha_pago >= desde)
    if hasta is not None:
        stmt = stmt.where(Pago.fecha_pago <= hasta)
    if q:
        termino = q.strip().lstrip("#")
        condiciones = [Pago.referencia_banco.ilike(f"%{termino}%")]
        if termino.isdigit():
            condiciones.append(Pago.orden_id == int(termino))
        stmt = stmt.where(or_(*condiciones))
    stmt = ordenar(
        stmt, orden_por, direccion,
        {
            "id": Pago.id,
            "orden_id": Pago.orden_id,
            "monto": Pago.monto,
            "estado": Pago.estado,
            "fecha_pago": Pago.fecha_pago,
            "proveedor": Pago.proveedor,
        },
        por_defecto=Pago.fecha_pago.desc(),
    )
    return await paginate(db, stmt, response, skip, limit)


def _solo_staff(scope: UserScope) -> None:
    """El registro/edición/borrado manual de pagos es exclusivo del staff. El cliente
    paga únicamente por checkout/MercadoPago (no puede marcar su pago como Pagado)."""
    if not scope.ve_todo():
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acción reservada al personal interno")


@router.post("/ordenes/{orden_id}/pagos", response_model=PagoResponse, status_code=status.HTTP_201_CREATED)
async def create_pago(
    orden_id: int,
    payload: PagoCreate,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("pagos", "write")),
):
    _solo_staff(scope)
    orden = await db.get(Orden, orden_id)
    if orden is None:
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    if orden.estado == "Cancelado":
        raise HTTPException(status_code=409, detail="No se puede registrar un pago de una orden cancelada")
    # Un solo pago confirmado por orden: evita dobles cobros accidentales.
    pagado_id = (
        await db.execute(
            select(Pago.id).where(Pago.orden_id == orden_id, Pago.estado == "Pagado").limit(1)
        )
    ).scalar_one_or_none()
    if pagado_id is not None:
        raise HTTPException(
            status_code=409,
            detail=f"La orden #{orden_id} ya tiene un pago confirmado (pago #{pagado_id}).",
        )
    # El monto debe coincidir con el total de la orden (coherencia contable). Si la
    # orden no tiene total calculado, se acepta el monto indicado.
    if orden.total is not None and Decimal(str(payload.monto)) != Decimal(str(orden.total)):
        raise HTTPException(
            status_code=400,
            detail=f"El monto ({payload.monto}) no coincide con el total de la orden ({orden.total}).",
        )
    pago = Pago(orden_id=orden_id, **payload.model_dump())
    db.add(pago)
    # Un pago manual confirmado libera la orden retenida por pago (mismo efecto que
    # el checkout): 'Pendiente de Pago' → 'Pendiente' (despachable).
    liberada = payload.estado == "Pagado" and orden.estado == "Pendiente de Pago"
    if liberada:
        pago.fecha_pago = datetime.now(timezone.utc)
        orden.estado = "Pendiente"
    await db.commit()
    await db.refresh(pago)
    if liberada:
        evento = {"tipo": "pago", "orden_id": orden.id, "estado": "Pagado"}
        await publish(canal_cliente(orden.cliente_id), evento)
        await publish(CANAL_STAFF, {"tipo": "orden", "accion": "estado", "orden_id": orden.id, "estado": orden.estado})
    return pago


@router.get("/ordenes/{orden_id}/pagos", response_model=list[PagoResponse])
async def list_pagos_orden(
    orden_id: int,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("pagos", "read")),
):
    orden = await db.get(Orden, orden_id)
    if orden is None or not await orden_en_alcance(db, scope, orden):
        raise HTTPException(status_code=404, detail="Orden no encontrada")
    result = await db.execute(select(Pago).where(Pago.orden_id == orden_id).order_by(Pago.fecha_pago.desc()))
    return result.scalars().all()


@router.get("/pagos/{pago_id}", response_model=PagoResponse)
async def get_pago(
    pago_id: int,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("pagos", "read")),
):
    pago = await db.get(Pago, pago_id)
    if pago is None:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    orden = await db.get(Orden, pago.orden_id)
    if orden is None or not await orden_en_alcance(db, scope, orden):
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    return pago


@router.patch("/pagos/{pago_id}", response_model=PagoResponse)
async def update_pago(
    pago_id: int,
    payload: PagoUpdate,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("pagos", "write")),
):
    _solo_staff(scope)
    pago = await db.get(Pago, pago_id)
    if pago is None:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    cambios = payload.model_dump(exclude_unset=True)
    for k, v in cambios.items():
        setattr(pago, k, v)
    # Al confirmar el pago (Pagado), sellar la fecha si el staff no la indicó: así el pago
    # entra en la ventana de "Recaudación 24h" del dashboard (igual que _confirmar_pago).
    if cambios.get("estado") == "Pagado" and "fecha_pago" not in cambios:
        pago.fecha_pago = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(pago)
    return pago


@router.delete("/pagos/{pago_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pago(
    pago_id: int,
    db: AsyncSession = Depends(get_db),
    scope: UserScope = Depends(get_scope),
    _: object = Depends(require_permiso("pagos", "delete")),
):
    _solo_staff(scope)
    pago = await db.get(Pago, pago_id)
    if pago is None:
        raise HTTPException(status_code=404, detail="Pago no encontrado")
    await db.delete(pago)
    await db.commit()
