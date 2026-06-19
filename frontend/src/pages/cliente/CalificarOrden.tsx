import { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Star } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Field } from "@/components/ui/Field";
import { PageLoader } from "@/components/ui/Feedback";
import type { Calificacion } from "@/types";

function Stars({ value, onChange }: { value: number; onChange?: (n: number) => void }) {
  const [hover, setHover] = useState(0);
  return (
    <div className="flex gap-1">
      {[1, 2, 3, 4, 5].map((n) => (
        <button
          key={n}
          type="button"
          disabled={!onChange}
          onMouseEnter={() => onChange && setHover(n)}
          onMouseLeave={() => setHover(0)}
          onClick={() => onChange?.(n)}
          className={onChange ? "cursor-pointer" : "cursor-default"}
        >
          <Star
            className={`h-8 w-8 ${(hover || value) >= n ? "fill-amber-400 text-amber-400" : "text-stone-300"}`}
          />
        </button>
      ))}
    </div>
  );
}

export default function CalificarOrden() {
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const ordenId = Number(id);

  const { data: existente, isLoading } = useQuery({
    queryKey: ["calificacion", ordenId],
    queryFn: async () => {
      try {
        const { data } = await api.get<Calificacion>(`/ordenes/${ordenId}/calificacion`);
        return data;
      } catch {
        return null;
      }
    },
    retry: false,
  });

  const [puntaje, setPuntaje] = useState(5);
  const [comentario, setComentario] = useState("");
  const [loading, setLoading] = useState(false);

  const enviar = async () => {
    setLoading(true);
    try {
      await api.post(`/ordenes/${ordenId}/calificacion`, { puntaje, comentario: comentario || null });
      qc.invalidateQueries({ queryKey: ["calificacion", ordenId] });
      toast.success("¡Gracias por tu calificación!");
      navigate("/");
    } catch (err) {
      toast.error(apiError(err));
    } finally {
      setLoading(false);
    }
  };

  if (isLoading) return <PageLoader />;

  return (
    <div className="mx-auto max-w-md space-y-4">
      <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-sm text-stone-500 hover:text-stone-700">
        <ArrowLeft className="h-4 w-4" /> Volver
      </button>
      <div className="rounded-2xl border border-sillar-300 bg-white p-6 shadow-soft">
        <h1 className="text-lg font-semibold text-stone-800">Calificar pedido #{ordenId}</h1>
        {existente ? (
          <div className="mt-4 space-y-3">
            <p className="text-sm text-stone-500">Ya calificaste este pedido:</p>
            <Stars value={existente.puntaje} />
            {existente.comentario && <p className="text-sm text-stone-600">“{existente.comentario}”</p>}
          </div>
        ) : (
          <div className="mt-4 space-y-4">
            <Field label="¿Cómo estuvo la entrega?">
              <Stars value={puntaje} onChange={setPuntaje} />
            </Field>
            <Field label="Comentario (opcional)">
              <textarea
                value={comentario}
                onChange={(e) => setComentario(e.target.value)}
                rows={3}
                placeholder="Cuéntanos tu experiencia…"
                className="w-full rounded-xl border border-sillar-300 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
              />
            </Field>
            <Button className="w-full" size="lg" loading={loading} onClick={enviar}>
              Enviar calificación
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
