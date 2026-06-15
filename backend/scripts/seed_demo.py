"""Puebla la plataforma con datos demo ambientados en Arequipa para probar cada módulo.

Crea: clientes + direcciones (con lat/lon), flota de vehículos, usuarios y conductores,
órdenes en todos los estados, asignaciones (Asignada / EnCurso / Finalizada con entrega),
rutas con paradas, pagos y facturas, incidencias; y en MongoDB: pings GPS (trails en vivo
e históricos), geocercas (corredores y zonas de entrega) y notificaciones.

Es idempotente: limpia los datos de dominio (no toca roles ni el usuario admin) y reinserta.

Uso (con el stack levantado):  docker compose exec api python -m scripts.seed_demo
"""
import asyncio
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select

from core.database import AsyncSessionLocal
from core.mongo import connect_to_mongo, close_mongo_connection, ensure_all_indexes, get_database
from core.security import hash_password
from models.asignaciones import Asignacion
from models.clientes import Cliente, ClienteDireccion
from models.conductores import Conductor
from models.incidencias import Incidencia
from models.ordenes import Factura, Orden, Pago
from models.roles import Permiso, Rol
from models.rutas import Parada, RutaPlanificada
from models.usuarios import Usuario
from models.vehiculos import Vehiculo

random.seed(2026)
now = datetime.now(timezone.utc)
DEMO_DOMAIN = "demo.rappi2.com"

# Distritos de Arequipa: (lat, lon)
AQP = {
    "Cercado": (-16.3989, -71.5350),
    "Yanahuara": (-16.3936, -71.5450),
    "Cayma": (-16.3760, -71.5490),
    "Cerro Colorado": (-16.3650, -71.5800),
    "José L. Bustamante y Rivero": (-16.4280, -71.5260),
    "Paucarpata": (-16.4200, -71.4900),
    "Sachaca": (-16.4150, -71.5700),
    "Socabaya": (-16.4600, -71.5300),
    "Miraflores": (-16.3900, -71.5180),
    "Mariano Melgar": (-16.4000, -71.5050),
}
DISTRITOS = list(AQP.items())

PERMS = {
    "Despachador": (
        [(r, a) for r in ["ordenes", "asignaciones", "rutas", "tracking", "clientes", "conductores", "vehiculos", "incidencias", "geocercas"] for a in ["read", "write"]]
        + [("reportes", "read"), ("pagos", "read"), ("facturas", "read")]
    ),
    "Conductor": [("tracking", "read"), ("tracking", "write"), ("ordenes", "read"), ("asignaciones", "read"), ("rutas", "read"), ("incidencias", "read"), ("incidencias", "write")],
    "Cliente": [("ordenes", "read"), ("tracking", "read")],
}


def lerp(a, b, t):
    return a + (b - a) * t


def punto(o, d, t):
    """Punto (lat, lon) a fracción t del segmento o->d."""
    return (lerp(o[0], d[0], t), lerp(o[1], d[1], t))


def corredor(o, d, pad=0.013):
    """Anillo GeoJSON [lon,lat] rodeando el segmento o->d (corredor de ruta)."""
    minlat, maxlat = min(o[0], d[0]) - pad, max(o[0], d[0]) + pad
    minlon, maxlon = min(o[1], d[1]) - pad, max(o[1], d[1]) + pad
    return [[minlon, minlat], [maxlon, minlat], [maxlon, maxlat], [minlon, maxlat], [minlon, minlat]]


def zona(center, r=0.012):
    la, lo = center
    return [[lo - r, la - r], [lo + r, la - r], [lo + r, la + r], [lo - r, la + r], [lo - r, la - r]]


async def limpiar(db):
    for model in [Incidencia, Parada, RutaPlanificada, Pago, Factura, Asignacion, Orden, ClienteDireccion, Conductor, Vehiculo, Cliente]:
        await db.execute(delete(model))
    await db.execute(delete(Usuario).where(Usuario.email.like(f"%@{DEMO_DOMAIN}")))
    await db.commit()


async def set_permisos(db, rol: Rol, pares):
    await db.execute(delete(Permiso).where(Permiso.rol_id == rol.id))
    for recurso, accion in pares:
        db.add(Permiso(rol_id=rol.id, recurso=recurso, accion=accion))
    await db.commit()


async def main():
    await connect_to_mongo()
    try:
        await ensure_all_indexes()
    except Exception:
        pass
    mongo = get_database()

    async with AsyncSessionLocal() as db:
        await limpiar(db)

        roles = {r.nombre: r for r in (await db.execute(select(Rol))).scalars().all()}
        for nombre in ["Despachador", "Conductor", "Cliente"]:
            if nombre not in roles:
                r = Rol(nombre=nombre)
                db.add(r)
                await db.flush()
                roles[nombre] = r
        await db.commit()
        for nombre, pares in PERMS.items():
            await set_permisos(db, roles[nombre], pares)

        # ---- Clientes + direcciones ----
        nombres_cli = [
            "Distribuidora del Misti SAC", "Farmacias Characato EIRL", "Textiles Yanahuara SAC",
            "Picantería La Nueva Palomino", "Minimarket Cayma Express", "Importadora Chachani SRL",
        ]
        clientes = []
        for i, nom in enumerate(nombres_cli):
            c = Cliente(nombre=nom, email=f"cliente{i+1}@{DEMO_DOMAIN}", telefono=f"95{random.randint(1000000,9999999)}", cc_id=f"20{random.randint(100000000,999999999)}")
            db.add(c)
            await db.flush()
            d1, c1 = DISTRITOS[i % len(DISTRITOS)]
            db.add(ClienteDireccion(cliente_id=c.id, direccion=f"Av. {d1} {random.randint(100,1999)}", distrito=d1, ciudad="Arequipa", pais="PE", lat=c1[0], lon=c1[1], es_principal=True))
            d2, c2 = DISTRITOS[(i + 3) % len(DISTRITOS)]
            db.add(ClienteDireccion(cliente_id=c.id, direccion=f"Calle {d2} {random.randint(100,999)}", distrito=d2, ciudad="Arequipa", pais="PE", lat=c2[0], lon=c2[1]))
            clientes.append(c)
        await db.commit()

        # ---- Vehículos ----
        vehiculos_def = [
            ("AQP-101", "Camioneta", 1500, "Operativo"), ("AQP-202", "Furgón", 3000, "Operativo"),
            ("AQP-303", "Motocarga", 90, "Operativo"), ("AQP-404", "Camión", 8000, "Operativo"),
            ("AQP-505", "Motocarga", 80, "Operativo"), ("AQP-606", "Van", 2000, "Operativo"),
            ("AQP-707", "Camión", 7000, "Mantenimiento"),
        ]
        for placa, tipo, cap, est in vehiculos_def:
            db.add(Vehiculo(placa=placa, tipo=tipo, capacidad_kg=cap, estado=est, activo=(est != "Inactivo")))
        await db.commit()

        # ---- Usuarios staff ----
        db.add(Usuario(username="despachador", email=f"despachador@{DEMO_DOMAIN}", password_hash=hash_password("demo123"), rol_id=roles["Despachador"].id))
        cliente_user = Usuario(username="cliente", email=f"cuenta.cliente@{DEMO_DOMAIN}", password_hash=hash_password("demo123"), rol_id=roles["Cliente"].id, cliente_id=clientes[0].id)
        db.add(cliente_user)
        await db.flush()

        # ---- Conductores (usuario + perfil) ----
        nombres_cond = ["Juan Mamani Quispe", "Rosa Huamaní Ccama", "Carlos Apaza Flores", "Lucía Choque Mamani", "Pedro Cáceres Zúñiga", "Ana Ticona Larico"]
        placas_op = ["AQP-101", "AQP-202", "AQP-303", "AQP-404", "AQP-505", "AQP-606"]
        conductores = []
        for i, nom in enumerate(nombres_cond):
            u = Usuario(username=f"conductor{i+1}", email=f"conductor{i+1}@{DEMO_DOMAIN}", password_hash=hash_password("demo123"), rol_id=roles["Conductor"].id)
            db.add(u)
            await db.flush()
            cond = Conductor(usuario_id=u.id, nombre=nom, licencia=f"Q{random.randint(10000000,99999999)}", disponibilidad="Disponible", vehiculo_placa=placas_op[i], activo=True)
            db.add(cond)
            await db.flush()
            conductores.append(cond)
        await db.commit()

        # ---- Órdenes + ciclo de vida ----
        # escenarios: (estado_orden, escenario, cliente_idx, cond_idx)
        escenarios = [
            ("Entregado", "fin", 0, 4), ("Entregado", "fin", 1, 5), ("Entregado", "fin", 2, 4),
            ("En Tránsito", "curso", 0, 0), ("En Tránsito", "curso_alerta", 3, 1),
            ("En Proceso", "asignada", 4, 2), ("En Proceso", "asignada", 1, 3),
            ("Pendiente", "pendiente", 5, None), ("Pendiente", "pendiente", 2, None),
            ("Cancelado", "cancelado", 3, None), ("Pendiente", "pendiente", 0, None), ("Pendiente", "pendiente", 4, None),
        ]
        ping_docs, geo_docs = [], []

        for idx, (estado, esc, ci, condi) in enumerate(escenarios):
            (do, co) = DISTRITOS[idx % len(DISTRITOS)]
            (dd, cd) = DISTRITOS[(idx + 4) % len(DISTRITOS)]
            orden = Orden(
                cliente_id=clientes[ci].id, estado=estado,
                direccion_origen=f"Almacén {do}", distrito_origen=do, lat_origen=co[0], lon_origen=co[1],
                direccion_destino=f"Av. {dd} {random.randint(100,1999)}", distrito_destino=dd, lat_destino=cd[0], lon_destino=cd[1],
                total=round(random.uniform(45, 480), 2),
                fecha_creacion=now - timedelta(days=random.randint(0, 18), hours=random.randint(0, 23)),
            )
            db.add(orden)
            await db.flush()

            if condi is None:
                continue

            cond = conductores[condi]
            asg = Asignacion(orden_id=orden.id, conductor_id=cond.id, vehiculo_placa=cond.vehiculo_placa)
            db.add(asg)
            await db.flush()  # asg.id disponible para los pings
            ruta_needed = esc in ("fin", "curso", "curso_alerta")

            if esc == "fin":
                ini = now - timedelta(days=random.randint(1, 6), minutes=random.randint(0, 200))
                asg.estado = "Finalizada"
                asg.fecha_inicio = ini
                asg.fecha_fin = ini + timedelta(minutes=random.randint(28, 75))
                asg.entrega_lat, asg.entrega_lon = cd[0], cd[1]
                asg.entrega_receptor = random.choice(["Recepción", "Portería", "Sr. Gutiérrez", "Sra. Mamani"])
                cond.disponibilidad = "Disponible"
                # trail histórico completo origen->destino
                base = asg.fecha_inicio
                for k in range(12):
                    p = punto(co, cd, k / 11)
                    ping_docs.append(_ping(asg, cond, p, base + timedelta(minutes=k * 4), 18 + random.random() * 22))
            elif esc in ("curso", "curso_alerta"):
                asg.estado = "EnCurso"
                asg.fecha_inicio = now - timedelta(minutes=28)
                cond.disponibilidad = "Ocupado"
                # trail reciente (en vivo): origen -> ~70% del camino
                for k in range(12):
                    frac = (k / 11) * 0.7
                    p = punto(co, cd, frac)
                    if esc == "curso_alerta" and k >= 10:
                        p = (p[0] + 0.03, p[1] + 0.03)  # se sale del corredor -> dispara alerta
                    ping_docs.append(_ping(asg, cond, p, now - timedelta(minutes=(11 - k) * 2.3), 12 + random.random() * 30))
            elif esc == "asignada":
                asg.estado = "Asignada"
                cond.disponibilidad = "Ocupado"

            if ruta_needed:
                ruta = RutaPlanificada(orden_id=orden.id, distancia_km=round(random.uniform(3, 16), 2), tiempo_estimado=timedelta(minutes=random.randint(15, 55)))
                visitado = esc == "fin"
                ruta.paradas.append(Parada(orden_id=orden.id, direccion=orden.direccion_origen, distrito=do, lat=co[0], lon=co[1], secuencia=1, estado="Visitada", fecha_paso=asg.fecha_inicio))
                ruta.paradas.append(Parada(orden_id=orden.id, direccion=orden.direccion_destino, distrito=dd, lat=cd[0], lon=cd[1], secuencia=2, estado="Visitada" if visitado else "Pendiente", fecha_paso=asg.fecha_fin if visitado else None))
                db.add(ruta)
                await db.flush()
                if esc in ("curso", "curso_alerta"):
                    geo_docs.append({"ruta_id": ruta.id, "orden_id": orden.id, "tipo": "ruta_buffer", "geometry": {"type": "Polygon", "coordinates": [corredor(co, cd)]}, "tolerance_m": 80, "activa": True, "created_at": now})

            # pagos / facturas para entregadas
            if esc == "fin":
                pago_fecha = now - timedelta(hours=random.choice([2, 6, 20, 30, 96, 200]))
                db.add(Pago(orden_id=orden.id, monto=orden.total, estado="Pagado", referencia_banco=f"OP-{random.randint(10000,99999)}", fecha_pago=pago_fecha))
                db.add(Factura(orden_id=orden.id, ruc="20456789012", monto=orden.total, url="https://comprobantes.demo/factura.pdf", fecha=pago_fecha))

        await db.commit()

        # pagos adicionales (para la serie de ventas de 30 días) sobre órdenes existentes
        ordenes_all = (await db.execute(select(Orden))).scalars().all()
        for _ in range(10):
            o = random.choice(ordenes_all)
            estado_pago = random.choices(["Pagado", "Pendiente", "Fallido"], weights=[7, 2, 1])[0]
            db.add(Pago(orden_id=o.id, monto=round(random.uniform(40, 300), 2), estado=estado_pago, referencia_banco=f"REF-{random.randint(1000,9999)}", fecha_pago=now - timedelta(days=random.randint(0, 29), hours=random.randint(0, 23))))
        await db.commit()

        # incidencias sobre asignaciones existentes
        asgs = (await db.execute(select(Asignacion))).scalars().all()
        tipos_inc = ["Retraso por tráfico", "Dirección incorrecta", "Cliente ausente", "Daño en paquete", "Clima adverso"]
        for a in random.sample(asgs, min(4, len(asgs))):
            db.add(Incidencia(asignacion_id=a.id, tipo=random.choice(tipos_inc), severidad=random.randint(2, 5), notas="Reportado por el conductor en ruta.", fecha=now - timedelta(hours=random.randint(1, 60))))
        await db.commit()

        admin = (await db.execute(select(Usuario).where(Usuario.username == "admin"))).scalar_one_or_none()
        admin_id = admin.id if admin else None

    # ---- MongoDB ----
    if ping_docs:
        await mongo["gps_tracking"].delete_many({})
        await mongo["gps_tracking"].insert_many(ping_docs)

    await mongo["geocercas"].delete_many({})
    geo_docs += [
        {"ruta_id": None, "orden_id": None, "tipo": "zona_entrega", "geometry": {"type": "Polygon", "coordinates": [zona(AQP["Cayma"])]}, "tolerance_m": None, "activa": True, "created_at": now},
        {"ruta_id": None, "orden_id": None, "tipo": "zona_entrega", "geometry": {"type": "Polygon", "coordinates": [zona(AQP["José L. Bustamante y Rivero"])]}, "tolerance_m": None, "activa": True, "created_at": now},
        {"ruta_id": None, "orden_id": None, "tipo": "prohibida", "geometry": {"type": "Polygon", "coordinates": [zona(AQP["Cercado"], 0.006)]}, "tolerance_m": None, "activa": True, "created_at": now},
    ]
    await mongo["geocercas"].insert_many(geo_docs)

    await mongo["notificaciones"].delete_many({"destinatario_tipo": {"$in": ["usuario", "cliente"]}})
    notifs = []
    if admin_id:
        notifs += [
            {"destinatario_tipo": "usuario", "destinatario_id": admin_id, "tipo": "orden", "titulo": "Nueva orden pendiente", "mensaje": "Una orden está esperando asignación.", "metadata": {}, "leida": False, "fecha": now - timedelta(minutes=12)},
            {"destinatario_tipo": "usuario", "destinatario_id": admin_id, "tipo": "alerta", "titulo": "Conductor fuera de ruta", "mensaje": "La orden en tránsito salió de su geocerca.", "metadata": {}, "leida": False, "fecha": now - timedelta(minutes=4)},
            {"destinatario_tipo": "usuario", "destinatario_id": admin_id, "tipo": "pago", "titulo": "Pago confirmado", "mensaje": "Se registró un pago en las últimas horas.", "metadata": {}, "leida": True, "fecha": now - timedelta(hours=3)},
        ]
    notifs += [
        {"destinatario_tipo": "cliente", "destinatario_id": clientes[0].id, "tipo": "envio", "titulo": "Tu pedido está en camino", "mensaje": "El conductor se dirige a tu dirección.", "metadata": {}, "leida": False, "fecha": now - timedelta(minutes=20)},
        {"destinatario_tipo": "cliente", "destinatario_id": clientes[0].id, "tipo": "envio", "titulo": "Pedido entregado", "mensaje": "Gracias por tu compra.", "metadata": {}, "leida": True, "fecha": now - timedelta(days=1)},
    ]
    await mongo["notificaciones"].insert_many(notifs)

    await close_mongo_connection()

    print("=" * 60)
    print("  Datos demo cargados (Arequipa) ✓")
    print("=" * 60)
    print(f"  Clientes: {len(clientes)} · Vehículos: {len(vehiculos_def)} · Conductores: {len(conductores)}")
    print(f"  Órdenes: {len(escenarios)} (todos los estados) · Pings GPS: {len(ping_docs)} · Geocercas: {len(geo_docs)}")
    print("  Usuarios de prueba (password: demo123):")
    print("    - admin / admin123        (Admin · todo)")
    print("    - despachador / demo123   (operación)")
    print("    - conductor1..6 / demo123 (conductor)")
    print("    - cliente / demo123       (rol Cliente · solo 'Mis órdenes')")
    print("=" * 60)


def _ping(asg, cond, p_latlon, ts, speed):
    return {
        "asignacion_id": asg.id,
        "conductor_id": cond.id,
        "vehiculo_placa": cond.vehiculo_placa,
        "location": {"type": "Point", "coordinates": [p_latlon[1], p_latlon[0]]},
        "speed_kmh": round(speed, 1),
        "heading": round(random.uniform(0, 360), 1),
        "accuracy_m": round(random.uniform(3, 12), 1),
        "timestamp": ts,
    }


if __name__ == "__main__":
    asyncio.run(main())
