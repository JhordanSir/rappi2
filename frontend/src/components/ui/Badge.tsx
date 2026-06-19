import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type Tone = "gray" | "blue" | "green" | "amber" | "red" | "indigo" | "purple" | "slate";

const tones: Record<Tone, string> = {
  gray: "bg-slate-100 text-slate-600 ring-slate-200",
  slate: "bg-slate-700/10 text-slate-700 ring-slate-300",
  blue: "bg-blue-50 text-blue-700 ring-blue-200",
  green: "bg-emerald-50 text-emerald-700 ring-emerald-200",
  amber: "bg-amber-50 text-amber-700 ring-amber-200",
  red: "bg-rose-50 text-rose-700 ring-rose-200",
  indigo: "bg-indigo-50 text-indigo-700 ring-indigo-200",
  purple: "bg-purple-50 text-purple-700 ring-purple-200",
};

export function Badge({ tone = "gray", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        tones[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

const ORDEN_TONE: Record<string, Tone> = {
  "Pendiente de Pago": "purple",
  Pendiente: "amber",
  "En Proceso": "blue",
  "En Tránsito": "indigo",
  Entregado: "green",
  Cancelado: "red",
};
const ASIGN_TONE: Record<string, Tone> = {
  Asignada: "blue",
  EnCurso: "indigo",
  Finalizada: "green",
  Cancelada: "red",
};
const DISPO_TONE: Record<string, Tone> = {
  Disponible: "green",
  Ocupado: "amber",
  Inactivo: "gray",
};
const VEHIC_TONE: Record<string, Tone> = {
  Operativo: "green",
  Mantenimiento: "amber",
  Inactivo: "gray",
};
const PARADA_TONE: Record<string, Tone> = {
  Pendiente: "amber",
  Visitada: "green",
  Omitida: "gray",
};
const PAGO_TONE: Record<string, Tone> = {
  Pendiente: "amber",
  Pagado: "green",
  Fallido: "red",
  Reembolsado: "purple",
};

export function StatusBadge({ kind, value }: { kind: "orden" | "asignacion" | "dispo" | "vehiculo" | "parada" | "pago"; value?: string | null }) {
  if (!value) return <Badge tone="gray">—</Badge>;
  const map =
    kind === "orden" ? ORDEN_TONE
    : kind === "asignacion" ? ASIGN_TONE
    : kind === "dispo" ? DISPO_TONE
    : kind === "vehiculo" ? VEHIC_TONE
    : kind === "parada" ? PARADA_TONE
    : PAGO_TONE;
  return <Badge tone={map[value] ?? "gray"}>{value}</Badge>;
}
