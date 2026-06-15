import { useState } from "react";
import {
  ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip, CartesianGrid, Cell,
} from "recharts";
import { DollarSign, FileText, Timer, TimerReset, TimerOff } from "lucide-react";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { StatCard } from "@/components/ui/StatCard";
import { DataTable } from "@/components/ui/Table";
import { Button } from "@/components/ui/Button";
import { Badge, StatusBadge } from "@/components/ui/Badge";
import { useReporte } from "@/api/hooks";
import { formatMoney, formatNumber, humanDuration, formatDate } from "@/lib/utils";

const SEV_COLORS = ["#94a3b8", "#a3e635", "#facc15", "#fb923c", "#f43f5e"];

export default function ReportesPage() {
  const [gran, setGran] = useState<"dia" | "mes">("dia");
  const { data: ventas } = useReporte<any>("ventas", { granularidad: gran });
  const { data: tiempos } = useReporte<any>("tiempos-entrega");
  const { data: inc } = useReporte<any>("incidencias");
  const { data: conductores } = useReporte<any[]>("conductores");

  const serieVentas = (ventas?.series ?? []).map((s: any) => ({ periodo: formatDate(s.periodo, false), monto: s.monto }));
  const sevData = Object.entries(inc?.por_severidad ?? {}).map(([s, n]) => ({ nivel: `Nivel ${s}`, n, idx: Number(s) - 1 }));

  return (
    <div>
      <PageHeader title="Reportes & KPIs" subtitle="Indicadores de ventas, entregas, incidencias y desempeño" />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Total recaudado" value={formatMoney(ventas?.total_recaudado)} icon={<DollarSign className="h-6 w-6" />} tone="green" hint={`${gran === "dia" ? "Últimos 30 días" : "Por mes"}`} />
        <StatCard label="Total facturado" value={formatMoney(ventas?.total_facturado)} icon={<FileText className="h-6 w-6" />} tone="indigo" />
        <StatCard label="Tiempo prom. entrega" value={humanDuration(tiempos?.tiempo_promedio_segundos)} icon={<Timer className="h-6 w-6" />} tone="brand" hint={`${formatNumber(tiempos?.asignaciones_finalizadas)} entregas`} />
        <StatCard label="Incidencias" value={formatNumber(inc?.total)} icon={<TimerOff className="h-6 w-6" />} tone="red" />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            title="Recaudación"
            subtitle="Pagos confirmados"
            action={
              <div className="flex rounded-lg bg-slate-100 p-0.5">
                {(["dia", "mes"] as const).map((g) => (
                  <Button key={g} size="sm" variant={gran === g ? "primary" : "ghost"} onClick={() => setGran(g)} className="capitalize">
                    {g === "dia" ? "Diario" : "Mensual"}
                  </Button>
                ))}
              </div>
            }
          />
          <CardBody>
            {serieVentas.length === 0 ? (
              <div className="flex h-64 items-center justify-center text-sm text-slate-400">Sin datos</div>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={serieVentas} margin={{ left: -16, right: 8, top: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                  <XAxis dataKey="periodo" tick={{ fontSize: 11, fill: "#94a3b8" }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} tickLine={false} axisLine={false} />
                  <Tooltip formatter={(v: any) => formatMoney(v)} contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 13 }} cursor={{ fill: "#f8fafc" }} />
                  <Bar dataKey="monto" fill="#0d9488" radius={[6, 6, 0, 0]} maxBarSize={42} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Incidencias por severidad" />
          <CardBody>
            {sevData.length === 0 ? (
              <div className="flex h-64 items-center justify-center text-sm text-slate-400">Sin incidencias</div>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={sevData} margin={{ left: -20, right: 8, top: 8 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                  <XAxis dataKey="nivel" tick={{ fontSize: 11, fill: "#94a3b8" }} tickLine={false} axisLine={false} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: "#94a3b8" }} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 13 }} cursor={{ fill: "#f8fafc" }} />
                  <Bar dataKey="n" radius={[6, 6, 0, 0]} maxBarSize={42}>
                    {sevData.map((d) => <Cell key={d.nivel} fill={SEV_COLORS[d.idx] ?? "#94a3b8"} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardBody>
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 lg:col-span-1 lg:grid-cols-1">
          <StatCard label="Entrega más rápida" value={humanDuration(tiempos?.tiempo_minimo_segundos)} icon={<TimerReset className="h-6 w-6" />} tone="green" />
          <StatCard label="Entrega más lenta" value={humanDuration(tiempos?.tiempo_maximo_segundos)} icon={<TimerOff className="h-6 w-6" />} tone="amber" />
          <StatCard label="Promedio (min)" value={`${formatNumber(tiempos?.tiempo_promedio_minutos, 1)} min`} icon={<Timer className="h-6 w-6" />} tone="brand" />
        </div>

        <Card className="lg:col-span-2">
          <CardHeader title="Desempeño por conductor" />
          <DataTable
            rows={conductores}
            rowKey={(c) => c.conductor_id}
            columns={[
              { header: "Conductor", cell: (c) => <span className="font-medium text-slate-800">{c.nombre}</span> },
              { header: "Disponibilidad", cell: (c) => <StatusBadge kind="dispo" value={c.disponibilidad} /> },
              { header: "Asignaciones", align: "right", cell: (c) => formatNumber(c.total_asignaciones) },
              { header: "Finalizadas", align: "right", cell: (c) => <Badge tone="green">{c.finalizadas}</Badge> },
              { header: "En curso", align: "right", cell: (c) => <Badge tone="indigo">{c.en_curso}</Badge> },
              { header: "Incidencias", align: "right", cell: (c) => <Badge tone={c.incidencias > 0 ? "red" : "gray"}>{c.incidencias}</Badge> },
            ]}
            empty="Sin datos de conductores"
          />
        </Card>
      </div>
    </div>
  );
}
