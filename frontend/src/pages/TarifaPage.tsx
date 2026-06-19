import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { useTarifa, useApiMutation } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Field, Input } from "@/components/ui/Field";
import { Button } from "@/components/ui/Button";
import { PageLoader } from "@/components/ui/Feedback";
import type { TarifaConfig } from "@/types";

type Form = Record<string, string>;

// Campos numéricos editables agrupados para la UI.
const SECCIONES: { titulo: string; subtitulo: string; campos: { key: keyof TarifaConfig; label: string; step?: string }[] }[] = [
  {
    titulo: "Tarifa base",
    subtitulo: "Componentes que se suman para el subtotal de cada tramo.",
    campos: [
      { key: "tarifa_base", label: "Cargo base (banderazo)" },
      { key: "precio_km", label: "Precio por km" },
      { key: "precio_min", label: "Precio por minuto" },
      { key: "precio_kg", label: "Precio por kg cobrable" },
      { key: "factor_volumetrico", label: "Factor volumétrico (cm³/kg)", step: "1" },
      { key: "minimo", label: "Precio mínimo" },
    ],
  },
  {
    titulo: "Multiplicadores de servicio",
    subtitulo: "Multiplican el subtotal según el nivel elegido por el cliente.",
    campos: [
      { key: "mult_estandar", label: "Estándar" },
      { key: "mult_express", label: "Express" },
      { key: "mult_urgente", label: "Urgente" },
    ],
  },
  {
    titulo: "Recargos por horario",
    subtitulo: "Porcentajes que se suman (p.ej. 0.20 = +20%). Las horas son locales (0–23).",
    campos: [
      { key: "recargo_nocturno_pct", label: "Recargo nocturno" },
      { key: "nocturno_desde", label: "Nocturno desde (hora)", step: "1" },
      { key: "nocturno_hasta", label: "Nocturno hasta (hora)", step: "1" },
      { key: "recargo_pico_pct", label: "Recargo hora pico" },
      { key: "recargo_finde_pct", label: "Recargo fin de semana" },
    ],
  },
];

const TODOS = SECCIONES.flatMap((s) => s.campos.map((c) => c.key));

export default function TarifaPage() {
  const { can } = useAuth();
  const { data: tarifa, isLoading } = useTarifa();
  const [form, setForm] = useState<Form>({});
  const puedeEditar = can("tarifa", "write");

  useEffect(() => {
    if (tarifa) {
      const f: Form = {};
      TODOS.forEach((k) => (f[k] = String(tarifa[k] ?? "")));
      setForm(f);
    }
  }, [tarifa]);

  const guardar = useApiMutation(
    (body: Record<string, number>) => api.patch("/tarifa/", body),
    ["tarifa"],
  );

  const onSave = async () => {
    const body: Record<string, number> = {};
    TODOS.forEach((k) => {
      const v = Number(form[k]);
      if (!Number.isNaN(v)) body[k] = v;
    });
    try {
      await guardar.mutateAsync(body);
      toast.success("Tarifa actualizada");
    } catch (err) {
      toast.error(apiError(err));
    }
  };

  if (isLoading || !tarifa) return <PageLoader />;

  return (
    <div>
      <PageHeader
        title="Configuración de tarifa"
        subtitle="Define cómo se calcula automáticamente el precio de cada envío."
        actions={puedeEditar && <Button onClick={onSave} loading={guardar.isPending}>Guardar cambios</Button>}
      />
      <div className="grid gap-5 lg:grid-cols-3">
        {SECCIONES.map((sec) => (
          <Card key={sec.titulo}>
            <CardHeader title={sec.titulo} subtitle={sec.subtitulo} />
            <CardBody className="space-y-3">
              {sec.campos.map((c) => (
                <Field key={c.key} label={c.label}>
                  <Input
                    type="number"
                    step={c.step ?? "0.01"}
                    value={form[c.key] ?? ""}
                    disabled={!puedeEditar}
                    onChange={(e) => setForm((f) => ({ ...f, [c.key]: e.target.value }))}
                  />
                </Field>
              ))}
            </CardBody>
          </Card>
        ))}
      </div>
      <p className="mt-4 text-xs text-slate-400">
        Moneda: {tarifa.moneda} · Ventanas de hora pico: {(tarifa.pico_ventanas || []).map((v) => `${v[0]}–${v[1]}h`).join(", ")}
      </p>
    </div>
  );
}
