import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { CreditCard, CheckCircle2, ShieldCheck } from "lucide-react";
import toast from "react-hot-toast";
import { useQueryClient } from "@tanstack/react-query";
import { useOrden } from "@/api/hooks";
import { api, apiError } from "@/lib/api";
import { formatMoney } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { PageLoader } from "@/components/ui/Feedback";

/** Checkout simulado (cuando MercadoPago no tiene llaves). Confirma el pago localmente. */
export default function PagoSimulado() {
  const [sp] = useSearchParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const ordenId = Number(sp.get("orden"));
  const { data: orden, isLoading } = useOrden(ordenId || undefined);
  const [paid, setPaid] = useState(false);
  const [loading, setLoading] = useState(false);

  const pagar = async () => {
    setLoading(true);
    try {
      await api.post(`/pagos/simular/${ordenId}`);
      setPaid(true);
      qc.invalidateQueries({ queryKey: ["mis-ordenes"] });
      toast.success("Pago confirmado");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setLoading(false);
    }
  };

  if (isLoading) return <PageLoader />;

  return (
    <div className="mx-auto max-w-md py-6">
      <div className="rounded-2xl border border-sillar-300 bg-white p-6 shadow-soft">
        {paid ? (
          <div className="text-center">
            <CheckCircle2 className="mx-auto h-14 w-14 text-emerald-500" />
            <h1 className="mt-3 text-lg font-semibold text-stone-800">¡Pago confirmado!</h1>
            <p className="mt-1 text-sm text-stone-500">Tu pedido #{ordenId} ya está en gestión.</p>
            <div className="mt-5 flex justify-center gap-2">
              <Button variant="outline" onClick={() => navigate("/")}>Mis pedidos</Button>
              <Button onClick={() => navigate(`/orden/${ordenId}`)}>Ver seguimiento</Button>
            </div>
          </div>
        ) : (
          <>
            <div className="flex items-center gap-2 text-brand-700">
              <CreditCard className="h-5 w-5" />
              <p className="font-semibold">Pago de tu pedido</p>
            </div>
            <div className="mt-4 rounded-xl bg-sillar-100 p-4">
              <p className="text-sm text-stone-500">Pedido #{ordenId}</p>
              <p className="mt-1 text-3xl font-bold text-stone-800">{formatMoney(orden?.total)}</p>
            </div>
            <Button className="mt-5 w-full" size="lg" loading={loading} onClick={pagar}>
              Pagar {formatMoney(orden?.total)}
            </Button>
            <p className="mt-3 flex items-center justify-center gap-1 text-xs text-stone-400">
              <ShieldCheck className="h-3.5 w-3.5" /> Checkout simulado (sin cargo real)
            </p>
          </>
        )}
      </div>
    </div>
  );
}
