import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, MapPin, Flag, Clock, Zap, Plus, Trash2 } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { iniciarCheckout } from "@/api/checkout";
import { LocationPicker, type LatLng } from "@/components/map/MapView";
import { COLORS } from "@/components/map/icons";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import type { Cotizacion, NivelServicio, Orden } from "@/types";

const NIVELES: { value: NivelServicio; label: string }[] = [
  { value: "estandar", label: "Estándar" },
  { value: "express", label: "Express" },
  { value: "urgente", label: "Urgente" },
];

interface DestinoForm {
  direccion: string;
  punto: LatLng | null;
  peso: string;
  largo: string;
  ancho: string;
  alto: string;
  nombre: string;
}

const nuevoDestino = (): DestinoForm => ({ direccion: "", punto: null, peso: "", largo: "", ancho: "", alto: "", nombre: "" });

export default function NuevoEnvio() {
  const navigate = useNavigate();
  const [dirOrigen, setDirOrigen] = useState("");
  const [origen, setOrigen] = useState<LatLng | null>(null);
  const [destinos, setDestinos] = useState<DestinoForm[]>([nuevoDestino()]);
  const [nivel, setNivel] = useState<NivelServicio>("estandar");
  const [programar, setProgramar] = useState(false);
  const [programadoPara, setProgramadoPara] = useState("");
  const [cotizacion, setCotizacion] = useState<Cotizacion | null>(null);
  const [cotizando, setCotizando] = useState(false);
  const [cotizaError, setCotizaError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const num = (v: string) => (v.trim() === "" ? null : Number(v));
  const programadoISO = () => (programar && programadoPara ? new Date(programadoPara).toISOString() : null);
  const setDest = (i: number, patch: Partial<DestinoForm>) =>
    setDestinos((ds) => ds.map((d, j) => (j === i ? { ...d, ...patch } : d)));

  // Geocodificacion inversa: al tocar el mapa, autocompleta la direccion (P9).
  const reverseGeocode = async (p: LatLng): Promise<string | null> => {
    try {
      const { data } = await api.get<{ direccion: string | null }>("/geo/reverse", {
        params: { lat: p[0], lon: p[1] },
      });
      return data.direccion;
    } catch {
      return null;
    }
  };

  const destinosPayload = () =>
    destinos
      .filter((d) => d.punto)
      .map((d) => ({
        direccion: d.direccion,
        lat: d.punto![0],
        lon: d.punto![1],
        peso_kg: num(d.peso),
        largo_cm: num(d.largo),
        ancho_cm: num(d.ancho),
        alto_cm: num(d.alto),
        nombre_destinatario: d.nombre || null,
      }));

  // Cotización en vivo (suma de tramos).
  useEffect(() => {
    const conPunto = destinos.filter((d) => d.punto);
    if (!origen || conPunto.length === 0) {
      setCotizacion(null);
      return;
    }
    setCotizando(true);
    setCotizaError(null);
    const t = setTimeout(async () => {
      try {
        const { data } = await api.post<Cotizacion>("/ordenes/cotizar", {
          lat_origen: origen[0],
          lon_origen: origen[1],
          nivel_servicio: nivel,
          programado_para: programadoISO(),
          destinos: destinosPayload().map(({ direccion, nombre_destinatario, ...rest }) => rest),
        });
        setCotizacion(data);
      } catch (err) {
        setCotizacion(null);
        setCotizaError(apiError(err));
      } finally {
        setCotizando(false);
      }
    }, 500);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [origen, destinos, nivel, programar, programadoPara]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dirOrigen || !origen) return toast.error("Indica y fija el punto de recojo");
    const ds = destinosPayload();
    if (ds.length === 0) return toast.error("Fija al menos un destino en el mapa");
    if (ds.some((d) => !d.direccion)) return toast.error("Cada destino necesita una dirección");
    if (programar && !programadoPara) return toast.error("Indica la fecha y hora de programación");
    setLoading(true);
    try {
      // El backend fuerza el cliente_id del token para usuarios con rol Cliente;
      // no enviamos 0 (provocaba "cliente_id invalido o inactivo").
      const { data } = await api.post<Orden>("/ordenes/", {
        direccion_origen: dirOrigen,
        lat_origen: origen[0],
        lon_origen: origen[1],
        nivel_servicio: nivel,
        programado_para: programadoISO(),
        destinos: ds,
      });
      toast.success("Pedido creado · continúa con el pago");
      await iniciarCheckout(data.id, navigate);
    } catch (err) {
      toast.error(apiError(err));
      setLoading(false);
    }
  };

  const moneda = cotizacion?.moneda ?? "S/";

  return (
    <div className="space-y-5">
      <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-sm text-stone-500 hover:text-stone-700">
        <ArrowLeft className="h-4 w-4" /> Volver
      </button>
      <h1 className="text-xl font-semibold text-stone-800">Nuevo envío</h1>

      <form onSubmit={submit} className="space-y-6">
        {/* Origen */}
        <div className="space-y-3 rounded-2xl border border-sillar-300 bg-white p-4 shadow-soft">
          <p className="flex items-center gap-1.5 text-sm font-semibold text-emerald-700">
            <MapPin className="h-4 w-4" /> Origen (recojo)
          </p>
          <Field label="Dirección" required>
            <Input value={dirOrigen} onChange={(e) => setDirOrigen(e.target.value)} placeholder="Av. ejemplo 123, distrito" />
          </Field>
          <LocationPicker
            value={origen}
            onChange={async (p) => {
              setOrigen(p);
              if (p) { const dir = await reverseGeocode(p); if (dir) setDirOrigen(dir); }
            }}
            color={COLORS.origen}
          />
          <p className="text-xs text-stone-400">Toca el mapa para fijar el punto de recojo (la dirección se completa sola).</p>
        </div>

        {/* Destinos */}
        {destinos.map((d, i) => (
          <div key={i} className="space-y-3 rounded-2xl border border-sillar-300 bg-white p-4 shadow-soft">
            <div className="flex items-center justify-between">
              <p className="flex items-center gap-1.5 text-sm font-semibold text-rose-600">
                <Flag className="h-4 w-4" /> Destino {i + 1}
              </p>
              {destinos.length > 1 && (
                <button type="button" onClick={() => setDestinos((ds) => ds.filter((_, j) => j !== i))} className="text-stone-400 hover:text-rose-500">
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Dirección" required>
                <Input value={d.direccion} onChange={(e) => setDest(i, { direccion: e.target.value })} placeholder="Calle ejemplo 456, distrito" />
              </Field>
              <Field label="Destinatario (opcional)">
                <Input value={d.nombre} onChange={(e) => setDest(i, { nombre: e.target.value })} placeholder="Nombre de quien recibe" />
              </Field>
            </div>
            <LocationPicker
              value={d.punto}
              onChange={async (p) => {
                setDest(i, { punto: p });
                if (p) { const dir = await reverseGeocode(p); if (dir) setDest(i, { direccion: dir }); }
              }}
              color={COLORS.destino}
            />
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              <Field label="Peso (kg)"><Input type="number" min="0" step="0.1" value={d.peso} onChange={(e) => setDest(i, { peso: e.target.value })} placeholder="0" /></Field>
              <Field label="Largo (cm)"><Input type="number" min="0" step="1" value={d.largo} onChange={(e) => setDest(i, { largo: e.target.value })} placeholder="0" /></Field>
              <Field label="Ancho (cm)"><Input type="number" min="0" step="1" value={d.ancho} onChange={(e) => setDest(i, { ancho: e.target.value })} placeholder="0" /></Field>
              <Field label="Alto (cm)"><Input type="number" min="0" step="1" value={d.alto} onChange={(e) => setDest(i, { alto: e.target.value })} placeholder="0" /></Field>
            </div>
          </div>
        ))}
        <Button type="button" variant="outline" onClick={() => setDestinos((ds) => [...ds, nuevoDestino()])}>
          <Plus className="h-4 w-4" /> Agregar destino
        </Button>

        {/* Servicio y programación */}
        <div className="grid gap-5 md:grid-cols-2">
          <div className="space-y-3 rounded-2xl border border-sillar-300 bg-white p-4 shadow-soft">
            <p className="flex items-center gap-1.5 text-sm font-semibold text-stone-700"><Zap className="h-4 w-4" /> Nivel de servicio</p>
            <Select value={nivel} onChange={(e) => setNivel(e.target.value as NivelServicio)}>
              {NIVELES.map((n) => <option key={n.value} value={n.value}>{n.label}</option>)}
            </Select>
          </div>
          <div className="space-y-3 rounded-2xl border border-sillar-300 bg-white p-4 shadow-soft">
            <p className="flex items-center gap-1.5 text-sm font-semibold text-stone-700"><Clock className="h-4 w-4" /> Programación</p>
            <label className="flex items-center gap-2 text-sm text-stone-600">
              <input type="checkbox" checked={programar} onChange={(e) => setProgramar(e.target.checked)} /> Programar para más tarde
            </label>
            {programar ? (
              <Input type="datetime-local" value={programadoPara} onChange={(e) => setProgramadoPara(e.target.value)} />
            ) : (
              <p className="text-xs text-stone-400">Envío inmediato.</p>
            )}
          </div>
        </div>

        {/* Cotización */}
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 shadow-soft">
          {!origen || destinosPayload().length === 0 ? (
            <p className="text-sm text-stone-500">Fija origen y al menos un destino para ver el precio calculado.</p>
          ) : cotizando ? (
            <p className="text-sm text-stone-500">Calculando precio…</p>
          ) : cotizaError ? (
            <p className="text-sm text-rose-600">No se pudo calcular el precio: {cotizaError}</p>
          ) : cotizacion ? (
            <div className="space-y-3">
              <div className="flex flex-wrap items-end justify-between gap-4">
                <div className="space-y-1">
                  <p className="text-xs uppercase tracking-wide text-emerald-700">Precio estimado{cotizacion.tramos.length > 1 ? " (suma de tramos)" : ""}</p>
                  <p className="text-3xl font-bold text-stone-800">{moneda} {cotizacion.total.toFixed(2)}</p>
                  <p className="text-xs text-stone-500">{cotizacion.distancia_km} km · {cotizacion.tiempo_min} min</p>
                </div>
                <Button type="submit" size="lg" loading={loading}>Crear y pagar</Button>
              </div>
              {cotizacion.tramos.length > 1 && (
                <ul className="space-y-1 border-t border-emerald-200 pt-2 text-xs text-stone-500">
                  {cotizacion.tramos.map((t, i) => (
                    <li key={i} className="flex justify-between">
                      <span>Destino {i + 1} · {t.distancia_km} km · {t.peso_cobrable_kg} kg</span>
                      <span className="font-medium text-stone-700">{moneda} {t.total.toFixed(2)}</span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ) : null}
        </div>
      </form>
    </div>
  );
}
