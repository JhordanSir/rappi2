import { useNavigate, useSearchParams } from "react-router-dom";
import { CheckCircle2, XCircle, Clock } from "lucide-react";
import { Button } from "@/components/ui/Button";

type Estado = "exito" | "fallo" | "pendiente";

const CONFIG: Record<Estado, { icon: typeof CheckCircle2; color: string; titulo: string; texto: string }> = {
  exito: {
    icon: CheckCircle2,
    color: "text-emerald-500",
    titulo: "¡Pago aprobado!",
    texto: "Tu pago fue confirmado. Ya estamos gestionando tu pedido.",
  },
  pendiente: {
    icon: Clock,
    color: "text-amber-500",
    titulo: "Pago pendiente",
    texto: "Tu pago está siendo procesado. Te avisaremos cuando se confirme.",
  },
  fallo: {
    icon: XCircle,
    color: "text-rose-500",
    titulo: "El pago no se completó",
    texto: "No se pudo procesar tu pago. Puedes intentarlo nuevamente desde tus pedidos.",
  },
};

/** Página de retorno tras pagar en MercadoPago (back_urls de Checkout Pro). */
export default function PagoEstado({ estado }: { estado: Estado }) {
  const [sp] = useSearchParams();
  const navigate = useNavigate();
  const ordenId = sp.get("orden");
  const cfg = CONFIG[estado];
  const Icon = cfg.icon;

  return (
    <div className="mx-auto max-w-md py-10">
      <div className="rounded-2xl border border-sillar-300 bg-white p-8 text-center shadow-soft">
        <Icon className={`mx-auto h-16 w-16 ${cfg.color}`} />
        <h1 className="mt-4 text-lg font-semibold text-stone-800">{cfg.titulo}</h1>
        <p className="mt-1 text-sm text-stone-500">{cfg.texto}</p>
        <div className="mt-6 flex justify-center gap-2">
          <Button variant="outline" onClick={() => navigate("/")}>Mis pedidos</Button>
          {estado === "exito" && ordenId && (
            <Button onClick={() => navigate(`/orden/${ordenId}`)}>Ver seguimiento</Button>
          )}
        </div>
      </div>
    </div>
  );
}
