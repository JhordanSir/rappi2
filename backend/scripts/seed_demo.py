"""Puebla la plataforma con datos demo ambientados en Arequipa para probar cada módulo.

Crea: clientes + direcciones (con lat/lon), flota de vehículos, usuarios y conductores,
órdenes en todos los estados (incluyendo MULTIDESTINO, un RUN AGRUPADO de varias órdenes,
entregas parciales con un destino fallido, ajustes de precio, niveles de servicio y envíos
programados), rutas multiparada, pagos y facturas, incidencias (chofer / automática / admin);
y en MongoDB: pings GPS, geocercas, notificaciones y EVIDENCIA real de entrega (imágenes).

Es idempotente: limpia los datos de dominio (no toca roles ni el usuario admin) y reinserta.

Uso (con el stack levantado):  docker compose exec api python -m scripts.seed_demo
"""
import asyncio
import os
import random
from datetime import datetime, timedelta, timezone

import httpx
from motor.motor_asyncio import AsyncIOMotorGridFSBucket
from sqlalchemy import delete, select

from core.database import AsyncSessionLocal
from core.mongo import connect_to_mongo, close_mongo_connection, ensure_all_indexes, get_database
from core.security import hash_password
from models.asignaciones import Asignacion
from models.calificaciones import Calificacion
from models.clientes import Cliente, ClienteDireccion
from models.destinos import Destino
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

# PDF público y estable para que el botón "Ver" de las facturas demo abra un comprobante real.
FACTURA_PDF_DEMO = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"

ASSETS = os.path.join(os.path.dirname(__file__), "assets")
# Imágenes de evidencia (se alternan en las entregas). La 1ª es liviana; la 2ª, pesada.
EVID_IMAGES = [("HK-yjwpXcAAmZ5Z.jpeg", "image/jpeg"), ("gopherrappi.png", "image/png")]

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
RECEPTORES = ["Sr. Gutiérrez", "Sra. Mamani", "Recepción", "Portería", "Farmacia Central", "Minimarket"]
PESOS = [3.0, 8.0, 1.5, 12.0, 5.0, 0.8, 20.0]

PERMS = {
    "Conductor": [("tracking", "read"), ("tracking", "write"), ("ordenes", "read"), ("asignaciones", "read"), ("asignaciones", "write"), ("rutas", "read"), ("rutas", "write"), ("incidencias", "read"), ("incidencias", "write"), ("entregas", "read"), ("entregas", "write"), ("conductores", "read"), ("calificaciones", "read"), ("notificaciones", "read")],
    "Cliente": [("ordenes", "read"), ("ordenes", "write"), ("tracking", "read"), ("pagos", "read"), ("pagos", "write"), ("clientes", "read"), ("clientes", "write"), ("incidencias", "read"), ("incidencias", "write"), ("calificaciones", "read"), ("calificaciones", "write"), ("facturas", "read"), ("notificaciones", "read")],
}


def lerp(a, b, t):
    return a + (b - a) * t


def punto(o, d, t):
    return (lerp(o[0], d[0], t), lerp(o[1], d[1], t))


def corredor(o, d, pad=0.013):
    minlat, maxlat = min(o[0], d[0]) - pad, max(o[0], d[0]) + pad
    minlon, maxlon = min(o[1], d[1]) - pad, max(o[1], d[1]) + pad
    return [[minlon, minlat], [maxlon, minlat], [maxlon, maxlat], [minlon, maxlat], [minlon, minlat]]


def zona(center, r=0.012):
    la, lo = center
    return [[lo - r, la - r], [lo + r, la - r], [lo + r, la + r], [lo - r, la + r], [lo - r, la - r]]


def resample(line, n):
    if not line or len(line) <= n:
        return line
    step = (len(line) - 1) / (n - 1)
    return [line[round(i * step)] for i in range(n)]


async def road_points(o, d, use_osrm=True):
    """Geometría real por calles (OSRM) como lista de (lat, lon). Fallback: línea recta.

    Con use_osrm=False se omite la red y se devuelve una polilínea recta sintética:
    la generación masiva crea decenas de rutas y no debe depender de OSRM."""
    if not use_osrm:
        return [punto(o, d, k / 13) for k in range(14)]
    url = f"https://router.project-osrm.org/route/v1/driving/{o[1]},{o[0]};{d[1]},{d[0]}?overview=full&geometries=geojson"
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            r = await client.get(url)
            coords = r.json()["routes"][0]["geometry"]["coordinates"]
        line = [(c[1], c[0]) for c in coords]
        if len(line) >= 2:
            return line
    except Exception:
        pass
    return [punto(o, d, k / 13) for k in range(14)]


def _estado_parada(estado_destino: str) -> str:
    return {"Entregado": "Visitada", "Fallida": "Omitida"}.get(estado_destino, "Pendiente")


async def limpiar(db):
    for model in [Incidencia, Calificacion, Parada, RutaPlanificada, Pago, Factura, Asignacion, Destino, Orden, ClienteDireccion, Conductor, Vehiculo, Cliente]:
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

    ping_docs, geo_docs, evid_specs = [], [], []

    async with AsyncSessionLocal() as db:
        await limpiar(db)

        roles = {r.nombre: r for r in (await db.execute(select(Rol))).scalars().all()}
        for nombre in ["Conductor", "Cliente"]:
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
            "Comercial Selva Alegre SAC", "Botica San Camilo EIRL", "Ferretería El Misti SRL",
            "Panadería La Chimba SAC", "Agroindustrias Majes SAC", "Calzados Paucarpata EIRL",
            "Editorial Volcán SAC", "Lácteos Aján SRL", "Repuestos Tingo SAC", "Bazar Río Seco EIRL",
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
            # Una tercera dirección (sucursal/depósito) para enriquecer el directorio del cliente.
            d3, c3 = DISTRITOS[(i + 6) % len(DISTRITOS)]
            db.add(ClienteDireccion(cliente_id=c.id, direccion=f"Urb. {d3} Mz. {random.randint(1,30)} Lt. {random.randint(1,20)}", distrito=d3, ciudad="Arequipa", pais="PE", lat=c3[0], lon=c3[1]))
            # Integridad (P2): todo cliente debe tener su usuario para iniciar sesion.
            db.add(Usuario(
                username=f"cliente{i+1}",
                email=f"cliente{i+1}@{DEMO_DOMAIN}",
                password_hash=hash_password("demo123"),
                rol_id=roles["Cliente"].id,
                cliente_id=c.id,
            ))
            clientes.append(c)
        await db.commit()

        # ---- Vehículos ---- (placa, tipo, cap_kg, estado, largo_cm, ancho_cm, alto_cm)
        # Dimensiones útiles de carga aproximadas por tipo (para validar cubicaje en asignaciones).
        vehiculos_def = [
            ("AQP-101", "Camioneta", 1500, "Operativo", 180, 140, 120), ("AQP-202", "Furgón", 3000, "Operativo", 320, 180, 190),
            ("AQP-303", "Motocarga", 90, "Operativo", 120, 90, 90), ("AQP-404", "Camión", 8000, "Operativo", 600, 240, 240),
            ("AQP-505", "Motocarga", 80, "Operativo", 110, 85, 85), ("AQP-606", "Van", 2000, "Operativo", 250, 160, 150),
            ("AQP-707", "Furgón", 3500, "Operativo", 340, 185, 195), ("AQP-808", "Camioneta", 1400, "Operativo", 175, 138, 118),
            ("AQP-909", "Motocarga", 85, "Operativo", 115, 88, 88), ("AQP-110", "Van", 2200, "Operativo", 260, 162, 152),
            ("AQP-220", "Camión", 7500, "Operativo", 580, 238, 238), ("AQP-330", "Motocarga", 95, "Operativo", 125, 92, 92),
            ("AQP-440", "Furgón", 3200, "Operativo", 325, 182, 192), ("AQP-550", "Camioneta", 1600, "Operativo", 185, 142, 122),
            ("AQP-660", "Camión", 6800, "Mantenimiento", 560, 235, 235), ("AQP-770", "Van", 2100, "Inactivo", 255, 160, 150),
        ]
        for placa, tipo, cap, est, largo, ancho, alto in vehiculos_def:
            db.add(Vehiculo(placa=placa, tipo=tipo, capacidad_kg=cap, estado=est, activo=(est != "Inactivo"),
                            largo_cm=largo, ancho_cm=ancho, alto_cm=alto))
        await db.commit()
        placas_operativas = [v[0] for v in vehiculos_def if v[3] == "Operativo"]

        # ---- Conductores (usuario + perfil) ----
        nombres_cond = [
            "Juan Mamani Quispe", "Rosa Huamaní Ccama", "Carlos Apaza Flores", "Lucía Choque Mamani",
            "Pedro Cáceres Zúñiga", "Ana Ticona Larico", "Miguel Condori Vilca", "Elena Quispe Ramos",
            "Jorge Salas Pinto", "Sofía Huanca Pari", "Raúl Ccahua Mendoza", "Diana Sucari Vargas",
            "Néstor Pacsi Llaza",
        ]
        placas_op = placas_operativas  # una placa operativa por conductor
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

        async def crear_orden(ci, estado, dlist, nivel="estandar", ajuste=None, prog_h=None, dest_estados=None):
            """Crea una orden con N destinos (dlist = lista de (distrito, (lat,lon)))."""
            (do, co) = DISTRITOS[random.randrange(len(DISTRITOS))]
            base = round(random.uniform(40, 140), 2)
            total = round(base * len(dlist) + (ajuste or 0), 2)
            o = Orden(
                cliente_id=clientes[ci].id, estado=estado,
                direccion_origen=f"Almacén {do}", distrito_origen=do, lat_origen=co[0], lon_origen=co[1],
                direccion_destino=f"Av. {dlist[0][0]} {random.randint(100,1999)}", distrito_destino=dlist[0][0],
                lat_destino=dlist[0][1][0], lon_destino=dlist[0][1][1],
                total=total, nivel_servicio=nivel,
                programado_para=(now + timedelta(hours=prog_h)) if prog_h else None,
                ajuste_monto=ajuste,
                ajuste_motivo=("Cliente frecuente" if ajuste and ajuste < 0 else ("Recargo zona alejada" if ajuste else None)),
                fecha_creacion=now - timedelta(days=random.randint(0, 18), hours=random.randint(0, 23)),
            )
            db.add(o)
            await db.flush()
            destinos = []
            for j, (dn, dc) in enumerate(dlist):
                de = (dest_estados or [None] * len(dlist))[j] or "Pendiente"
                d = Destino(
                    orden_id=o.id, secuencia=j + 1,
                    direccion=f"Av. {dn} {random.randint(100,1999)}", distrito=dn, lat=dc[0], lon=dc[1],
                    peso_kg=PESOS[(j + ci) % len(PESOS)], nombre_destinatario=random.choice(RECEPTORES),
                    subtotal=base, estado=de,
                    entrega_receptor=(random.choice(RECEPTORES) if de == "Entregado" else None),
                    fecha_entrega=(now - timedelta(hours=random.randint(1, 80)) if de in ("Entregado", "Fallida") else None),
                    nota=("Cliente ausente al momento de la entrega" if de == "Fallida" else None),
                )
                db.add(d)
                await db.flush()
                destinos.append(d)
            return o, (co, do), destinos

        async def crear_ruta(o, origen_latlon, do, destinos, origen_estado, fecha_inicio=None, fecha_fin=None, corredor_geo=False, use_osrm=True):
            road = await road_points(origen_latlon, (float(destinos[-1].lat), float(destinos[-1].lon)), use_osrm=use_osrm)
            geom = {"type": "LineString", "coordinates": [[p[1], p[0]] for p in road]}
            ruta = RutaPlanificada(orden_id=o.id, distancia_km=round(random.uniform(3, 16), 2), tiempo_estimado=timedelta(minutes=random.randint(15, 55)), geometria=geom)
            ruta.paradas.append(Parada(orden_id=o.id, direccion=o.direccion_origen, distrito=do, lat=origen_latlon[0], lon=origen_latlon[1], secuencia=1, estado=origen_estado, fecha_paso=fecha_inicio))
            for k, d in enumerate(destinos):
                pe = _estado_parada(d.estado)
                ruta.paradas.append(Parada(orden_id=o.id, destino_id=d.id, direccion=d.direccion, distrito=d.distrito, lat=d.lat, lon=d.lon, secuencia=2 + k, estado=pe, fecha_paso=(fecha_fin if pe in ("Visitada", "Omitida") else None)))
            db.add(ruta)
            await db.flush()
            if corredor_geo:
                geo_docs.append({"ruta_id": ruta.id, "orden_id": o.id, "tipo": "ruta_buffer", "geometry": {"type": "Polygon", "coordinates": [corredor(origen_latlon, (float(destinos[-1].lat), float(destinos[-1].lon)))]}, "tolerance_m": 80, "activa": True, "created_at": now})
            return ruta, road

        def add_evid(asg, destinos, uploaded_by, ts):
            for d in destinos:
                if d.estado == "Entregado":
                    evid_specs.append({
                        "asignacion_id": asg.id, "destino_id": d.id,
                        "receptor": d.entrega_receptor or "Recepción",
                        "lat": float(d.lat), "lon": float(d.lon), "ts": ts,
                        "img": len(evid_specs),
                    })

        # ---- Escenarios principales (uno por combinación, con multidestino variado) ----
        # (estado, esc, cliente, conductor, lista_de_distritos_destino, nivel, ajuste, prog_h)
        def dl(n, start):
            return [DISTRITOS[(start + j) % len(DISTRITOS)] for j in range(n)]

        escenarios = [
            ("Entregado", "fin", 0, 4, dl(1, 4), "estandar", None, None),
            ("Entregado", "fin", 1, 5, dl(3, 1), "express", -15, None),     # multidestino entregado
            ("Entregado", "fin_parcial", 2, 0, dl(2, 6), "estandar", None, None),  # 1 entregado + 1 fallido
            ("En Tránsito", "curso", 3, 1, dl(2, 2), "urgente", None, None),  # multidestino en curso
            ("En Tránsito", "curso_alerta", 4, 2, dl(1, 7), "estandar", None, None),
            ("En Proceso", "asignada", 5, 3, dl(2, 3), "estandar", 20, None),
            ("Pendiente", "pendiente", 1, None, dl(3, 0), "estandar", None, None),  # multidestino pendiente
            ("Pendiente", "pendiente", 2, None, dl(1, 5), "express", None, 8),       # programado
            ("Cancelado", "cancelado", 3, None, dl(1, 9), "estandar", None, None),
            ("Pendiente de Pago", "porpagar", 0, None, dl(2, 2), "express", None, 24),  # cliente sin pagar
            ("Pendiente", "pendiente", 4, None, dl(1, 1), "estandar", -8, None),
        ]

        for estado, esc, ci, condi, dlist, nivel, ajuste, prog_h in escenarios:
            if esc == "fin":
                dest_estados = ["Entregado"] * len(dlist)
            elif esc == "fin_parcial":
                dest_estados = ["Entregado"] + ["Fallida"] * (len(dlist) - 1)
            else:
                dest_estados = None
            o, (co, do), destinos = await crear_orden(ci, estado, dlist, nivel, ajuste, prog_h, dest_estados)

            if condi is None:
                continue
            cond = conductores[condi]
            asg = Asignacion(orden_id=o.id, conductor_id=cond.id, vehiculo_placa=cond.vehiculo_placa)
            asg.ordenes = [o]
            db.add(asg)
            await db.flush()

            origen_latlon = (co, do)
            if esc in ("fin", "fin_parcial"):
                ini = now - timedelta(days=random.randint(1, 6), minutes=random.randint(0, 200))
                fin = ini + timedelta(minutes=random.randint(28, 75))
                asg.estado, asg.fecha_inicio, asg.fecha_fin = "Finalizada", ini, fin
                asg.entrega_receptor = random.choice(RECEPTORES)
                cond.disponibilidad = "Disponible"
                ruta, road = await crear_ruta(o, (co[0], co[1]), do, destinos, "Visitada", ini, fin, corredor_geo=False)
                for k, p in enumerate(resample(road, 12)):
                    ping_docs.append(_ping(asg, cond, p, ini + timedelta(minutes=k * 4), 18 + random.random() * 22))
                add_evid(asg, destinos, cond.usuario_id, fin)
            elif esc in ("curso", "curso_alerta"):
                asg.estado, asg.fecha_inicio = "EnCurso", now - timedelta(minutes=28)
                cond.disponibilidad = "Ocupado"
                ruta, road = await crear_ruta(o, (co[0], co[1]), do, destinos, "Visitada", asg.fecha_inicio, None, corredor_geo=True)
                cut = max(2, int(len(road) * 0.7))
                pts = resample(road[:cut], 12)
                n = len(pts)
                for k, p in enumerate(pts):
                    if esc == "curso_alerta" and k >= n - 2:
                        p = (p[0] + 0.03, p[1] + 0.03)  # fuera del corredor
                    ping_docs.append(_ping(asg, cond, p, now - timedelta(minutes=(n - 1 - k) * 2.3), 12 + random.random() * 30))
                if esc == "curso_alerta":
                    db.add(Incidencia(asignacion_id=asg.id, tipo="Desvío de ruta", severidad=4, origen="automatica", notas="Detección automática: el conductor salió del corredor.", fecha=now - timedelta(minutes=6)))
            elif esc == "asignada":
                asg.estado = "Asignada"
                cond.disponibilidad = "Ocupado"
                await crear_ruta(o, (co[0], co[1]), do, destinos, "Pendiente", None, None, corredor_geo=False)

            if esc in ("fin", "fin_parcial"):
                pago_fecha = now - timedelta(hours=random.choice([2, 6, 20, 30, 96, 200]))
                db.add(Pago(orden_id=o.id, monto=o.total, estado="Pagado", referencia_banco=f"OP-{random.randint(10000,99999)}", fecha_pago=pago_fecha))
                db.add(Factura(orden_id=o.id, ruc="20456789012", monto=o.total, url=FACTURA_PDF_DEMO, fecha=pago_fecha))

        await db.commit()

        # ---- RUN AGRUPADO: 2 órdenes de un cliente en una sola ruta de un conductor, en curso ----
        gcond = conductores[5]  # Ana Ticona (conductor6), Van AQP-606 (cap 2000)
        run_orders, run_destinos = [], []
        for k in range(2):
            o, (co, do), destinos = await crear_orden(0, "En Tránsito", dl(1, k * 3), "estandar")
            run_orders.append((o, co, do))
            run_destinos.append(destinos[0])
        primary = run_orders[0][0]
        gasg = Asignacion(orden_id=primary.id, conductor_id=gcond.id, vehiculo_placa=gcond.vehiculo_placa, estado="EnCurso", fecha_inicio=now - timedelta(minutes=18))
        gasg.ordenes = [o for o, _, _ in run_orders]
        db.add(gasg)
        await db.flush()
        gcond.disponibilidad = "Ocupado"
        # Ruta consolidada: recojos de ambas órdenes + las dos entregas.
        o0, co0, do0 = run_orders[0]
        road = await road_points((co0[0], co0[1]), (float(run_destinos[-1].lat), float(run_destinos[-1].lon)))
        gruta = RutaPlanificada(orden_id=primary.id, distancia_km=round(random.uniform(6, 18), 2), tiempo_estimado=timedelta(minutes=random.randint(25, 60)), geometria={"type": "LineString", "coordinates": [[p[1], p[0]] for p in road]})
        seq = 1
        for o, co, do in run_orders:
            gruta.paradas.append(Parada(orden_id=o.id, direccion=o.direccion_origen, distrito=do, lat=co[0], lon=co[1], secuencia=seq, estado="Visitada", fecha_paso=gasg.fecha_inicio))
            seq += 1
        for d in run_destinos:
            gruta.paradas.append(Parada(orden_id=d.orden_id, destino_id=d.id, direccion=d.direccion, distrito=d.distrito, lat=d.lat, lon=d.lon, secuencia=seq, estado="Pendiente"))
            seq += 1
        db.add(gruta)
        await db.flush()
        geo_docs.append({"ruta_id": gruta.id, "orden_id": primary.id, "tipo": "ruta_buffer", "geometry": {"type": "Polygon", "coordinates": [corredor((co0[0], co0[1]), (float(run_destinos[-1].lat), float(run_destinos[-1].lon)), pad=0.02)]}, "tolerance_m": 90, "activa": True, "created_at": now})
        for k, p in enumerate(resample(road[: max(2, int(len(road) * 0.4))], 8)):
            ping_docs.append(_ping(gasg, gcond, p, now - timedelta(minutes=(8 - k) * 2), 15 + random.random() * 20))
        await db.commit()

        # ====== GENERACIÓN MASIVA: volumen en todas las tablas para explorar a fondo ======
        # Rutas SINTÉTICAS (use_osrm=False): no se golpea la red con decenas de órdenes.
        comentarios_pos = [
            "Entrega rápida y el conductor muy amable.", "Todo perfecto, paquete en buen estado.",
            "Excelente servicio, llegó antes de lo previsto.", "Muy buena comunicación durante el envío.",
            "El conductor fue muy cordial. Recomendado.", "Sin novedades, todo en orden.",
        ]
        comentarios_neg = [
            "Llegó con retraso pero el paquete estaba bien.", "El conductor tardó en ubicar la dirección.",
            "Esperaba un poco más de cuidado con el paquete.",
        ]
        MAX_ACTIVOS = 4            # tope de órdenes activas (EnCurso/Asignada) → deja conductores disponibles
        bulk_activos = 0
        recientes_forzadas = 3     # primeras finalizadas con fecha muy reciente → KPIs de últimas 24h

        # Más "Entregado" para que las series mensuales (≈12 meses) tengan varias barras por mes.
        estados_bulk = (
            ["Entregado"] * 48 + ["En Tránsito"] * 4 + ["En Proceso"] * 4 +
            ["Pendiente"] * 12 + ["Pendiente de Pago"] * 5 + ["Cancelado"] * 6
        )
        random.shuffle(estados_bulk)
        niveles_bulk = ["estandar", "estandar", "estandar", "express", "urgente"]

        for estado in estados_bulk:
            ci = random.randrange(len(clientes))
            multi = estado in ("Entregado", "En Tránsito", "En Proceso", "Pendiente")
            ndest = random.choices([1, 2, 3], weights=[6, 3, 2])[0] if multi else 1
            dlist = dl(ndest, random.randrange(len(DISTRITOS)))
            nivel = random.choice(niveles_bulk)
            ajuste = random.choice([None, None, None, -10, -5, 15, 25])
            prog_h = random.choice([None, None, None, 6, 12, 24, 48]) if estado in ("Pendiente", "Pendiente de Pago") else None

            if estado == "Entregado":
                parcial = ndest > 1 and random.random() < 0.18
                dest_estados = (["Entregado"] * (ndest - 1) + ["Fallida"]) if parcial else ["Entregado"] * ndest
            else:
                dest_estados = None

            o, (co, do), destinos = await crear_orden(ci, estado, dlist, nivel, ajuste, prog_h, dest_estados)
            # Distribuir la creación en ~12 meses → series mensuales ricas (ventas por día/mes).
            dias_atras = random.randint(0, 365)
            o.fecha_creacion = now - timedelta(days=dias_atras, hours=random.randint(0, 23), minutes=random.randint(0, 59))
            origen_latlon = (co[0], co[1])

            # --- Estados sin conductor ---
            if estado == "Pendiente":
                continue
            if estado == "Pendiente de Pago":
                db.add(Pago(orden_id=o.id, monto=o.total, estado="Pendiente", metodo="mercadopago", proveedor="mercadopago", fecha_pago=o.fecha_creacion))
                continue
            if estado == "Cancelado":
                if random.random() < 0.4:
                    db.add(Pago(orden_id=o.id, monto=o.total, estado="Fallido", referencia_banco=f"REF-{random.randint(1000,9999)}", fecha_pago=o.fecha_creacion))
                continue

            # --- Estados con conductor (Entregado / En Tránsito / En Proceso) ---
            if estado in ("En Tránsito", "En Proceso"):
                disponibles = [c for c in conductores if c.disponibilidad == "Disponible"]
                if bulk_activos >= MAX_ACTIVOS or not disponibles:
                    o.estado = "Pendiente"   # sin presupuesto de actividad → queda pendiente
                    continue
                cond = random.choice(disponibles)
            else:
                cond = random.choice(conductores)  # finalizada (histórica): no cambia disponibilidad

            asg = Asignacion(orden_id=o.id, conductor_id=cond.id, vehiculo_placa=cond.vehiculo_placa)
            asg.ordenes = [o]
            db.add(asg)
            await db.flush()

            if estado == "Entregado":
                if recientes_forzadas > 0:
                    fin = now - timedelta(hours=random.randint(1, 20))
                    recientes_forzadas -= 1
                else:
                    fin = now - timedelta(days=dias_atras, hours=random.randint(0, 12))
                ini = fin - timedelta(minutes=random.randint(25, 80))
                asg.estado, asg.fecha_inicio, asg.fecha_fin = "Finalizada", ini, fin
                asg.entrega_receptor = random.choice(RECEPTORES)
                ruta, road = await crear_ruta(o, origen_latlon, do, destinos, "Visitada", ini, fin, use_osrm=False)
                if random.random() < 0.45:  # solo una muestra lleva pings (controla el volumen en Mongo)
                    for k, p in enumerate(resample(road, 10)):
                        ping_docs.append(_ping(asg, cond, p, ini + timedelta(minutes=k * 5), 18 + random.random() * 20))
                if len(evid_specs) < 22:  # cap de evidencias (suben imágenes reales a GridFS)
                    add_evid(asg, destinos, cond.usuario_id, fin)
                pago_fecha = min(fin + timedelta(minutes=random.randint(2, 90)), now)
                db.add(Pago(orden_id=o.id, monto=o.total, estado="Pagado", referencia_banco=f"OP-{random.randint(10000,99999)}", metodo="mercadopago", proveedor="mercadopago", fecha_pago=pago_fecha))
                db.add(Factura(orden_id=o.id, ruc="20456789012", monto=o.total, url=FACTURA_PDF_DEMO, fecha=pago_fecha))
            else:
                bulk_activos += 1
                cond.disponibilidad = "Ocupado"
                if estado == "En Tránsito":
                    asg.estado, asg.fecha_inicio = "EnCurso", now - timedelta(minutes=random.randint(8, 45))
                    ruta, road = await crear_ruta(o, origen_latlon, do, destinos, "Visitada", asg.fecha_inicio, None, corredor_geo=True, use_osrm=False)
                    pts = resample(road[: max(2, int(len(road) * 0.65))], 10)
                    n = len(pts)
                    for k, p in enumerate(pts):
                        ping_docs.append(_ping(asg, cond, p, now - timedelta(minutes=(n - 1 - k) * 2.2), 12 + random.random() * 28))
                    if random.random() < 0.3:
                        db.add(Incidencia(asignacion_id=asg.id, tipo=random.choice(["Retraso por tráfico", "Clima adverso"]), severidad=random.randint(2, 3), origen="chofer", notas="Reportado por el conductor en ruta.", fecha=now - timedelta(minutes=random.randint(2, 25))))
                else:  # En Proceso → Asignada (aún sin iniciar)
                    asg.estado = "Asignada"
                    await crear_ruta(o, origen_latlon, do, destinos, "Pendiente", None, None, use_osrm=False)

        await db.commit()

        # ---- Incidencias variadas (chofer / admin), además de las automáticas ya creadas ----
        asgs = (await db.execute(select(Asignacion))).scalars().all()
        finalizadas = [a for a in asgs if a.estado == "Finalizada"]
        encurso = [a for a in asgs if a.estado == "EnCurso"]
        tipos_chofer = ["Retraso por tráfico", "Dirección incorrecta", "Cliente ausente", "Daño en paquete", "Clima adverso"]
        for a in random.sample(encurso + finalizadas, min(4, len(asgs))):
            db.add(Incidencia(asignacion_id=a.id, tipo=random.choice(tipos_chofer), severidad=random.randint(2, 4), origen="chofer", notas="Reportado por el conductor en ruta.", fecha=now - timedelta(hours=random.randint(1, 60))))
        if finalizadas:
            db.add(Incidencia(asignacion_id=finalizadas[0].id, tipo="Cierre forzado", severidad=2, origen="admin", notas="Entrega confirmada por teléfono con el cliente.", fecha=now - timedelta(hours=2)))
        await db.commit()

        # pagos adicionales para la serie de ventas
        ordenes_all = (await db.execute(select(Orden))).scalars().all()
        for _ in range(12):
            o = random.choice(ordenes_all)
            estado_pago = random.choices(["Pagado", "Pendiente", "Fallido"], weights=[7, 2, 1])[0]
            db.add(Pago(orden_id=o.id, monto=round(random.uniform(40, 300), 2), estado=estado_pago, referencia_banco=f"REF-{random.randint(1000,9999)}", fecha_pago=now - timedelta(days=random.randint(0, 29), hours=random.randint(0, 23))))
        await db.commit()

        # ---- Calificaciones: el cliente puntúa la entrega/conductor de las órdenes entregadas ----
        entregadas = (
            await db.execute(
                select(Orden.id, Orden.cliente_id, Asignacion.conductor_id, Asignacion.fecha_fin)
                .join(Asignacion, Asignacion.orden_id == Orden.id)
                .where(Orden.estado == "Entregado", Asignacion.estado == "Finalizada")
            )
        ).all()
        total_calificaciones = 0
        for oid, cli_id, cond_id, ffin in entregadas:
            if random.random() >= 0.82:  # no todos los clientes califican
                continue
            puntaje = random.choices([5, 4, 3, 2, 1], weights=[50, 30, 12, 5, 3])[0]
            if puntaje >= 4:
                comentario = random.choice(comentarios_pos) if random.random() < 0.7 else None
            else:
                comentario = random.choice(comentarios_neg)
            fecha = min((ffin or now) + timedelta(hours=random.randint(1, 48)), now)
            db.add(Calificacion(orden_id=oid, conductor_id=cond_id, cliente_id=cli_id, puntaje=puntaje, comentario=comentario, fecha=fecha))
            total_calificaciones += 1
        await db.commit()

        admin = (await db.execute(select(Usuario).where(Usuario.username == "admin"))).scalar_one_or_none()
        admin_id = admin.id if admin else None
        total_ordenes = len(ordenes_all)

    # ---- MongoDB: GPS, geocercas, evidencia, notificaciones ----
    if ping_docs:
        await mongo["gps_tracking"].delete_many({})
        await mongo["gps_tracking"].insert_many(ping_docs)

    await mongo["geocercas"].delete_many({})
    geo_docs += [
        {"ruta_id": None, "orden_id": None, "tipo": "zona_entrega", "geometry": {"type": "Polygon", "coordinates": [zona(AQP["Cayma"])]}, "tolerance_m": None, "activa": True, "created_at": now},
        {"ruta_id": None, "orden_id": None, "tipo": "zona_entrega", "geometry": {"type": "Polygon", "coordinates": [zona(AQP["José L. Bustamante y Rivero"])]}, "tolerance_m": None, "activa": True, "created_at": now},
        {"ruta_id": None, "orden_id": None, "tipo": "prohibida", "geometry": {"type": "Polygon", "coordinates": [zona(AQP["Cercado"], 0.006)]}, "tolerance_m": None, "activa": True, "created_at": now},
        # Plaqueo: centro histórico (Plaza de Armas / Cercado). Zona editable por el admin.
        {"ruta_id": None, "orden_id": None, "tipo": "restriccion_vehicular", "geometry": {"type": "Polygon", "coordinates": [zona((-16.3988, -71.5369), 0.006)]}, "tolerance_m": None, "activa": True, "created_at": now},
        {"ruta_id": None, "orden_id": None, "tipo": "zona_entrega", "geometry": {"type": "Polygon", "coordinates": [zona(AQP["Cerro Colorado"])]}, "tolerance_m": None, "activa": True, "created_at": now},
        {"ruta_id": None, "orden_id": None, "tipo": "zona_entrega", "geometry": {"type": "Polygon", "coordinates": [zona(AQP["Paucarpata"])]}, "tolerance_m": None, "activa": True, "created_at": now},
        {"ruta_id": None, "orden_id": None, "tipo": "zona_entrega", "geometry": {"type": "Polygon", "coordinates": [zona(AQP["Socabaya"])]}, "tolerance_m": None, "activa": True, "created_at": now},
        # Geocerca inactiva (para probar el filtro activa/inactiva en el panel).
        {"ruta_id": None, "orden_id": None, "tipo": "prohibida", "geometry": {"type": "Polygon", "coordinates": [zona(AQP["Miraflores"], 0.005)]}, "tolerance_m": None, "activa": False, "created_at": now},
    ]
    await mongo["geocercas"].insert_many(geo_docs)

    # Evidencia de entrega (imágenes reales en GridFS) para los destinos entregados.
    await mongo["entregas"].delete_many({})
    for coll in ("entregas_files.files", "entregas_files.chunks"):
        await mongo[coll].delete_many({})
    from services.imaging import comprimir_imagen
    bucket = AsyncIOMotorGridFSBucket(mongo, bucket_name="entregas_files")
    cache = {}
    for spec in evid_specs:
        name, ctype0 = EVID_IMAGES[spec["img"] % len(EVID_IMAGES)]
        if name not in cache:
            with open(os.path.join(ASSETS, name), "rb") as f:
                cache[name] = comprimir_imagen(f.read(), ctype0, name)  # (data, ctype, fname)
        data, ctype, fname = cache[name]
        file_id = await bucket.upload_from_stream(fname, data, metadata={"content_type": ctype, "asignacion_id": spec["asignacion_id"], "uploaded_by": admin_id})
        await mongo["entregas"].insert_one({
            "asignacion_id": spec["asignacion_id"], "destino_id": spec["destino_id"],
            "archivos": [{"file_id": str(file_id), "filename": fname, "content_type": ctype, "size": len(data)}],
            "tipo": "foto", "descripcion": f"Entrega destino #{spec['destino_id']}",
            "lat": spec["lat"], "lon": spec["lon"], "receptor": spec["receptor"],
            "uploaded_by": admin_id, "timestamp": spec["ts"],
        })

    await mongo["notificaciones"].delete_many({"destinatario_tipo": {"$in": ["usuario", "cliente"]}})
    notifs = []
    if admin_id:
        notifs += [
            {"destinatario_tipo": "usuario", "destinatario_id": admin_id, "tipo": "orden", "titulo": "Nueva orden pendiente", "mensaje": "Una orden está esperando asignación.", "metadata": {}, "leida": False, "fecha": now - timedelta(minutes=12)},
            {"destinatario_tipo": "usuario", "destinatario_id": admin_id, "tipo": "alerta", "titulo": "Conductor fuera de ruta", "mensaje": "La orden en tránsito salió de su geocerca.", "metadata": {}, "leida": False, "fecha": now - timedelta(minutes=4)},
            {"destinatario_tipo": "usuario", "destinatario_id": admin_id, "tipo": "pago", "titulo": "Pago confirmado", "mensaje": "Se registró un pago en las últimas horas.", "metadata": {}, "leida": True, "fecha": now - timedelta(hours=3)},
            {"destinatario_tipo": "usuario", "destinatario_id": admin_id, "tipo": "incidencia", "titulo": "Incidencia de severidad alta", "mensaje": "Una entrega reportó una incidencia que requiere revisión.", "metadata": {}, "leida": False, "fecha": now - timedelta(hours=1)},
            {"destinatario_tipo": "usuario", "destinatario_id": admin_id, "tipo": "sistema", "titulo": "Resumen diario disponible", "mensaje": "El reporte de operaciones del día ya está listo.", "metadata": {}, "leida": True, "fecha": now - timedelta(hours=8)},
        ]
    # Campana del cliente: varias por cada cliente (mezcla leídas / pendientes).
    cli_msgs = [
        ("envio", "Tu pedido está en camino", "El conductor se dirige a tu dirección."),
        ("envio", "Pedido entregado", "Gracias por tu compra."),
        ("pago", "Pago confirmado", "Tu pago fue procesado correctamente."),
        ("orden", "Pedido registrado", "Tu pedido fue creado y está pendiente de pago."),
    ]
    for c in clientes:
        for tipo, titulo, msg in random.sample(cli_msgs, k=random.randint(2, 4)):
            notifs.append({"destinatario_tipo": "cliente", "destinatario_id": c.id, "tipo": tipo, "titulo": titulo, "mensaje": msg, "metadata": {}, "leida": random.random() < 0.5, "fecha": now - timedelta(hours=random.randint(1, 240))})
    # App del conductor: notificaciones a su usuario.
    cond_msgs = [
        ("asignacion", "Nueva asignación", "Tienes una entrega asignada para hoy."),
        ("ruta", "Ruta actualizada", "Se actualizó tu ruta de reparto."),
        ("incidencia", "Incidencia registrada", "Tu reporte fue recibido por la central."),
    ]
    for cond in conductores:
        for tipo, titulo, msg in random.sample(cond_msgs, k=random.randint(1, 3)):
            notifs.append({"destinatario_tipo": "usuario", "destinatario_id": cond.usuario_id, "tipo": tipo, "titulo": titulo, "mensaje": msg, "metadata": {}, "leida": random.random() < 0.6, "fecha": now - timedelta(hours=random.randint(1, 180))})
    await mongo["notificaciones"].insert_many(notifs)

    await close_mongo_connection()

    print("=" * 60)
    print("  Datos demo AMPLIADOS cargados (Arequipa) ✓")
    print("=" * 60)
    print(f"  Clientes: {len(clientes)} · Vehículos: {len(vehiculos_def)} · Conductores: {len(conductores)}")
    print(f"  Órdenes: {total_ordenes} (multidestino, run agrupado, parcial, programadas, ajustes)")
    print(f"  Calificaciones: {total_calificaciones} · Notificaciones: {len(notifs)}")
    print(f"  Pings GPS: {len(ping_docs)} · Geocercas: {len(geo_docs)} · Evidencias (fotos): {len(evid_specs)}")
    print("  Usuarios: admin/admin123 · cliente1..%d/demo123 · conductor1..%d/demo123" % (len(clientes), len(conductores)))
    print("  Para probar:")
    print("    - admin / admin123        → reportes con volumen (ventas, ratings, SLA), evidencia, run agrupado")
    print("    - conductor6 / demo123    → RUN AGRUPADO (2 órdenes) en curso, entregar/no entregar por destino")
    print("    - conductor2 / demo123    → entrega en curso con multidestino")
    print("    - cliente1 / demo123      → sus pedidos (incluye multidestino) y prueba de entrega")
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
