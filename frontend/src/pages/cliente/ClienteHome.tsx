import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, CreditCard, MapPin, Star, Package } from "lucide-react";
import toast from "react-hot-toast";
import { usePaginated } from "@/api/hooks";
import { iniciarCheckout } from "@/api/checkout";
import { apiError } from "@/lib/api";
import { formatMoney, formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { StatusBadge } from "@/components/ui/Badge";
import { Select } from "@/components/ui/Field";
import { Pagination } from "@/components/ui/Pagination";
import { PageLoader } from "@/components/ui/Feedback";
import type { Orden } from "@/types";

const PAGE_SIZE = 8;
const FILTROS_ESTADO = ["Pendiente de Pago", "Pendiente", "En Proceso", "En Tránsito", "Entregado", "Cancelado"];

export default function ClienteHome() {
  const navigate = useNavigate();
  const [page, setPage] = useState(0);
  const [estado, setEstado] = useState("");
  const [paying, setPaying] = useState<number | null>(null);
  useEffect(() => setPage(0), [estado]);
  const { data, isLoading } = usePaginated<Orden>("mis-ordenes", "/ordenes/", {
    skip: page * PAGE_SIZE,
    limit: PAGE_SIZE,
    ...(estado ? { estado } : {}),
  });

  const pagar = async (id: number) => {
    setPaying(id);
    try {
      await iniciarCheckout(id, navigate);
    } catch (err) {
      toast.error(apiError(err));
      setPaying(null);
    }
  };

  const items = data?.items ?? [];

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-stone-800">Mis pedidos</h1>
          <p className="text-sm text-stone-500">Crea, paga y rastrea tus envíos.</p>
        </div>
        <Button onClick={() => navigate("/nuevo")}>
          <Plus className="h-4 w-4" /> Nuevo envío
        </Button>
      </div>

      {/* Historial: filtra activas vs entregadas/canceladas (el backend ya lo soporta). */}
      <Select value={estado} onChange={(e) => setEstado(e.target.value)} className="h-10 w-auto" title="Filtrar por estado">
        <option value="">Todos mis pedidos</option>
        {FILTROS_ESTADO.map((s) => <option key={s} value={s}>{s}</option>)}
      </Select>

      {isLoading ? (
        <PageLoader />
      ) : items.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-sillar-300 bg-white p-10 text-center">
          <Package className="mx-auto h-10 w-10 text-stone-300" />
          <p className="mt-3 text-sm text-stone-500">{estado ? "No tienes pedidos con ese estado." : "Aún no tienes pedidos."}</p>
          {!estado && (
            <Button className="mt-4" onClick={() => navigate("/nuevo")}>
              <Plus className="h-4 w-4" /> Crear mi primer envío
            </Button>
          )}
        </div>
      ) : (
        <div className="overflow-hidden rounded-2xl border border-sillar-300 bg-white shadow-soft">
          <ul className="divide-y divide-sillar-100">
            {items.map((o) => (
              <li key={o.id} className="flex flex-wrap items-center gap-3 px-4 py-3.5">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-semibold text-stone-800">Pedido #{o.id}</span>
                    <StatusBadge kind="orden" value={o.estado} />
                  </div>
                  <p title={o.direccion_destino} className="mt-0.5 flex items-center gap-1 truncate text-xs text-stone-500">
                    <MapPin className="h-3 w-3 shrink-0" /> {o.direccion_destino}
                  </p>
                  <p className="text-[11px] text-stone-400">{formatDate(o.fecha_creacion)} · {formatMoney(o.total)}</p>
                </div>
                <div className="flex items-center gap-2">
                  {o.estado === "Pendiente de Pago" && (
                    <Button size="sm" loading={paying === o.id} onClick={() => pagar(o.id)}>
                      <CreditCard className="h-4 w-4" /> Pagar
                    </Button>
                  )}
                  {/* Las canceladas también se pueden abrir (historial/soporte). */}
                  {o.estado !== "Pendiente de Pago" && (
                    <Button size="sm" variant="outline" onClick={() => navigate(`/orden/${o.id}`)}>
                      {o.estado === "Entregado" || o.estado === "Cancelado" ? "Ver" : "Seguir"}
                    </Button>
                  )}
                  {o.estado === "Entregado" && (
                    <Button size="sm" variant="outline" onClick={() => navigate(`/orden/${o.id}/calificar`)}>
                      <Star className="h-4 w-4" /> Calificar
                    </Button>
                  )}
                </div>
              </li>
            ))}
          </ul>
          <Pagination page={page} pageSize={PAGE_SIZE} total={data?.total ?? 0} onPageChange={setPage} />
        </div>
      )}
    </div>
  );
}
