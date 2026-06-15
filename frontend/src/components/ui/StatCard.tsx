import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

type Tone = "brand" | "green" | "amber" | "red" | "indigo" | "slate";

const toneMap: Record<Tone, string> = {
  brand: "bg-brand-50 text-brand-600",
  green: "bg-emerald-50 text-emerald-600",
  amber: "bg-amber-50 text-amber-600",
  red: "bg-rose-50 text-rose-600",
  indigo: "bg-indigo-50 text-indigo-600",
  slate: "bg-slate-100 text-slate-600",
};

export function StatCard({
  label,
  value,
  icon,
  tone = "brand",
  hint,
}: {
  label: string;
  value: ReactNode;
  icon?: ReactNode;
  tone?: Tone;
  hint?: ReactNode;
}) {
  return (
    <div className="card flex items-center gap-4 p-5">
      {icon && <div className={cn("flex h-12 w-12 shrink-0 items-center justify-center rounded-xl", toneMap[tone])}>{icon}</div>}
      <div className="min-w-0">
        <p className="truncate text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p>
        <p className="mt-0.5 text-2xl font-bold tracking-tight text-slate-900">{value}</p>
        {hint && <p className="mt-0.5 text-xs text-slate-400">{hint}</p>}
      </div>
    </div>
  );
}
