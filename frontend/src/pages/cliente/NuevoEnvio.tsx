import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowLeft, MapPin, Flag } from "lucide-react";
import toast from "react-hot-toast";
import { useAuth } from "@/auth/AuthContext";
import { api, apiError } from "@/lib/api";
import { iniciarCheckout } from "@/api/checkout";
import { LocationPicker, type LatLng } from "@/components/map/MapView";
import { COLORS } from "@/components/map/icons";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import type { Orden } from "@/types";

export default function NuevoEnvio() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [dirOrigen, setDirOrigen] = useState("");
  const [origen, setOrigen] = useState<LatLng | null>(null);
  const [dirDestino, setDirDestino] = useState("");
  const [destino, setDestino] = useState<LatLng | null>(null);
  const [total, setTotal] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!dirOrigen || !dirDestino) return toast.error("Indica las direcciones de origen y destino");
    if (!total || Number(total) <= 0) return toast.error("Indica el monto a pagar");
    setLoading(true);
    try {
      const { data } = await api.post<Orden>("/ordenes/", {
        cliente_id: user?.cliente_id ?? 0,
        direccion_origen: dirOrigen,
        lat_origen: origen?.[0] ?? null,
        lon_origen: origen?.[1] ?? null,
        direccion_destino: dirDestino,
        lat_destino: destino?.[0] ?? null,
        lon_destino: destino?.[1] ?? null,
        total: Number(total),
      });
      toast.success("Pedido creado · continúa con el pago");
      await iniciarCheckout(data.id, navigate);
    } catch (err) {
      toast.error(apiError(err));
      setLoading(false);
    }
  };

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
        <div className="flex flex-wrap items-end justify-between gap-4 rounded-2xl border border-sillar-300 bg-white p-4 shadow-soft">
          <Field label="Monto a pagar (S/)" required>
            <Input type="number" min="1" step="0.01" value={total} onChange={(e) => setTotal(e.target.value)} placeholder="0.00" className="w-40" />
          </Field>
          <Button type="submit" size="lg" loading={loading}>
            Crear y pagar
          </Button>
        </div>
      </form>
    </div>
  );
}
