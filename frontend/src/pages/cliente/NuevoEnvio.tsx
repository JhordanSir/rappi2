import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, MapPin, Flag, Package, Clock, Zap } from "lucide-react";
import toast from "react-hot-toast";
import { useAuth } from "@/auth/AuthContext";
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

export default function NuevoEnvio() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [dirOrigen, setDirOrigen] = useState("");
  const [origen, setOrigen] = useState<LatLng | null>(null);
  const [dirDestino, setDirDestino] = useState("");
  const [destino, setDestino] = useState<LatLng | null>(null);
  const [peso, setPeso] = useState("");
  const [largo, setLargo] = useState("");
  const [ancho, setAncho] = useState("");
  const [alto, setAlto] = useState("");
  const [nivel, setNivel] = useState<NivelServicio>("estandar");
  const [programar, setProgramar] = useState(false);
  const [programadoPara, setProgramadoPara] = useState("");
  const [cotizacion, setCotizacion] = useState<Cotizacion | null>(null);
  const [cotizando, setCotizando] = useState(false);
  const [cotizaError, setCotizaError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const num = (v: string) => (v.trim() === "" ? null : Number(v));
  const programadoISO = () => (programar && programadoPara ? new Date(programadoPara).toISOString() : null);

  // Cotización en vivo: cada vez que cambian origen/destino/paquete/servicio/horario.
  useEffect(() => {
    if (!origen || !destino) {
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
          lat_destino: destino[0],
          lon_destino: destino[1],
          peso_kg: num(peso),
          largo_cm: num(largo),
          ancho_cm: num(ancho),
          alto_cm: num(alto),
          nivel_servicio: nivel,
          programado_para: programadoISO(),
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
  }, [origen, destino, peso, largo, ancho, alto, nivel, programar, programadoPara]);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dirOrigen || !dirDestino) return toast.error("Indica las direcciones de origen y destino");
    if (!origen || !destino) return toast.error("Fija el punto de recojo y de entrega en el mapa");
    if (programar && !programadoPara) return toast.error("Indica la fecha y hora de programación");
    setLoading(true);
    try {
      const { data } = await api.post<Orden>("/ordenes/", {
        cliente_id: user?.cliente_id ?? 0,
        direccion_origen: dirOrigen,
        lat_origen: origen[0],
        lon_origen: origen[1],
        direccion_destino: dirDestino,
        lat_destino: destino[0],
        lon_destino: destino[1],
        peso_kg: num(peso),
        largo_cm: num(largo),
        ancho_cm: num(ancho),
        alto_cm: num(alto),
        nivel_servicio: nivel,
        programado_para: programadoISO(),
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
        <div className="grid gap-5 md:grid-cols-2">
          <div className="space-y-3 rounded-2xl border border-sillar-300 bg-white p-4 shadow-soft">
            <p className="flex items-center gap-1.5 text-sm font-semibold text-emerald-700">
              <MapPin className="h-4 w-4" /> Origen (recojo)
            </p>
            <Field label="Dirección" required>
              <Input value={dirOrigen} onChange={(e) => setDirOrigen(e.target.value)} placeholder="Av. ejemplo 123, distrito" />
            </Field>
            <LocationPicker value={origen} onChange={setOrigen} color={COLORS.origen} />
            <p className="text-xs text-stone-400">Toca el mapa para fijar el punto de recojo.</p>
          </div>
          <div className="space-y-3 rounded-2xl border border-sillar-300 bg-white p-4 shadow-soft">
            <p className="flex items-center gap-1.5 text-sm font-semibold text-rose-600">
              <Flag className="h-4 w-4" /> Destino (entrega)
            </p>
            <Field label="Dirección" required>
              <Input value={dirDestino} onChange={(e) => setDirDestino(e.target.value)} placeholder="Calle ejemplo 456, distrito" />
            </Field>
            <LocationPicker value={destino} onChange={setDestino} color={COLORS.destino} />
            <p className="text-xs text-stone-400">Toca el mapa para fijar el punto de entrega.</p>
          </div>
        </div>

        {/* Paquete */}
        <div className="space-y-3 rounded-2xl border border-sillar-300 bg-white p-4 shadow-soft">
          <p className="flex items-center gap-1.5 text-sm font-semibold text-stone-700">
            <Package className="h-4 w-4" /> Paquete
          </p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Field label="Peso (kg)">
              <Input type="number" min="0" step="0.1" value={peso} onChange={(e) => setPeso(e.target.value)} placeholder="0" />
            </Field>
            <Field label="Largo (cm)">
              <Input type="number" min="0" step="1" value={largo} onChange={(e) => setLargo(e.target.value)} placeholder="0" />
            </Field>
            <Field label="Ancho (cm)">
              <Input type="number" min="0" step="1" value={ancho} onChange={(e) => setAncho(e.target.value)} placeholder="0" />
            </Field>
            <Field label="Alto (cm)">
              <Input type="number" min="0" step="1" value={alto} onChange={(e) => setAlto(e.target.value)} placeholder="0" />
            </Field>
          </div>
          <p className="text-xs text-stone-400">Se cobra por el mayor entre el peso real y el peso volumétrico.</p>
        </div>

        {/* Servicio y programación */}
        <div className="grid gap-5 md:grid-cols-2">
          <div className="space-y-3 rounded-2xl border border-sillar-300 bg-white p-4 shadow-soft">
            <p className="flex items-center gap-1.5 text-sm font-semibold text-stone-700">
              <Zap className="h-4 w-4" /> Nivel de servicio
            </p>
            <Select value={nivel} onChange={(e) => setNivel(e.target.value as NivelServicio)}>
              {NIVELES.map((n) => (
                <option key={n.value} value={n.value}>{n.label}</option>
              ))}
            </Select>
          </div>
          <div className="space-y-3 rounded-2xl border border-sillar-300 bg-white p-4 shadow-soft">
            <p className="flex items-center gap-1.5 text-sm font-semibold text-stone-700">
              <Clock className="h-4 w-4" /> Programación
            </p>
            <label className="flex items-center gap-2 text-sm text-stone-600">
              <input type="checkbox" checked={programar} onChange={(e) => setProgramar(e.target.checked)} />
              Programar para más tarde
            </label>
            {programar ? (
              <Input type="datetime-local" value={programadoPara} onChange={(e) => setProgramadoPara(e.target.value)} />
            ) : (
              <p className="text-xs text-stone-400">Envío inmediato.</p>
            )}
          </div>
        </div>

        {/* Cotización en vivo */}
        <div className="rounded-2xl border border-emerald-200 bg-emerald-50 p-4 shadow-soft">
          {!origen || !destino ? (
            <p className="text-sm text-stone-500">Fija origen y destino para ver el precio calculado.</p>
          ) : cotizando ? (
            <p className="text-sm text-stone-500">Calculando precio…</p>
          ) : cotizaError ? (
            <p className="text-sm text-rose-600">No se pudo calcular el precio: {cotizaError}</p>
          ) : cotizacion ? (
            <div className="flex flex-wrap items-end justify-between gap-4">
              <div className="space-y-1 text-sm text-stone-600">
                <p className="text-xs uppercase tracking-wide text-emerald-700">Precio estimado</p>
                <p className="text-3xl font-bold text-stone-800">{moneda} {cotizacion.total.toFixed(2)}</p>
                <p className="text-xs text-stone-500">
                  {cotizacion.distancia_km} km · {cotizacion.tiempo_min} min · peso cobrable {cotizacion.peso_cobrable_kg} kg
                  {cotizacion.recargo_horario_pct > 0 && ` · recargo horario +${Math.round(cotizacion.recargo_horario_pct * 100)}%`}
                  {cotizacion.multiplicador_servicio !== 1 && ` · servicio ×${cotizacion.multiplicador_servicio}`}
                </p>
              </div>
              <Button type="submit" size="lg" loading={loading}>
                Crear y pagar
              </Button>
            </div>
          ) : null}
        </div>
      </form>
    </div>
  );
}
