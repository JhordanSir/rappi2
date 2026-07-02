import { Link } from "react-router-dom";
import {
  Package,
  Truck,
  Users,
  DollarSign,
  Activity,
  Navigation,
  ShieldAlert,
  Boxes,
  AlertTriangle,
} from "lucide-react";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import { PageHeader } from "@/components/ui/PageHeader";
import { StatCard } from "@/components/ui/StatCard";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { PageLoader } from "@/components/ui/Feedback";
import { DataTable } from "@/components/ui/Table";
import { useReporte } from "@/api/hooks";
import { formatMoney, formatNumber, formatDate } from "@/lib/utils";
import type { DashboardKPIs } from "@/types";

const ESTADO_COLORS: Record<string, string> = {
  Pendiente: "#f59e0b",
  "En Proceso": "#3b82f6",
  "En Tránsito": "#6366f1",
  Entregado: "#10b981",
  Cancelado: "#f43f5e",
};

export default function DashboardPage() {
  const { data: kpi, isLoading } = useReporte<DashboardKPIs>("dashboard");
  const { data: oper } = useReporte<Record<string, any>>("operativo");
  const { data: ventas } = useReporte<any>("ventas", { granularidad: "dia" });
  const { data: top } = useReporte<any[]>("top-clientes", { limit: 5 });

  if (isLoading || !kpi) return <PageLoader />;

  const totales = kpi.totales ?? {};
  const estados = Object.entries(kpi.ordenes_por_estado ?? {}).map(([name, value]) => ({ name, value }));
  const serie = (ventas?.series ?? []).map((s: any) => ({
    periodo: formatDate(s.periodo, false),
    monto: s.monto,
  }));

  return (
    <div>
      <PageHeader title="Dashboard" subtitle="Resumen operativo y comercial de la plataforma" />

      {/* Órdenes retenidas por pago hace días: no se auto-cancelan; el staff decide. */}
      {(kpi.ordenes_impagas_antiguas ?? 0) > 0 && (
        <Link
          to="/ordenes?estado=Pendiente%20de%20Pago"
          className="mb-4 flex items-center gap-3 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800 transition hover:bg-amber-100"
        >
          <AlertTriangle className="h-5 w-5 shrink-0 text-amber-500" />
          <span>
            <strong>{formatNumber(kpi.ordenes_impagas_antiguas)}</strong>{" "}
            {kpi.ordenes_impagas_antiguas === 1 ? "orden lleva" : "órdenes llevan"} más de{" "}
            {kpi.pago_aviso_dias ?? 2} días en «Pendiente de Pago» — revísalas para cobrar o cancelar.
          </span>
        </Link>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label="Órdenes totales" value={formatNumber(totales.ordenes)} icon={<Package className="h-6 w-6" />} tone="brand" />
        <StatCard
          label="En curso ahora"
          value={formatNumber(oper?.asignaciones_en_curso ?? 0)}
          icon={<Activity className="h-6 w-6" />}
          tone="indigo"
          hint={`${formatNumber(oper?.conductores_online ?? 0)} conductores en línea`}
        />
        <StatCard
          label="Conductores"
          value={formatNumber(totales.conductores)}
          icon={<Users className="h-6 w-6" />}
          tone="green"
          hint={`${formatNumber(kpi.conductores_por_disponibilidad?.Disponible ?? 0)} disponibles`}
        />
        <StatCard
          label="Recaudación 24h"
          value={formatMoney(kpi.recaudacion_ultimas_24h)}
          icon={<DollarSign className="h-6 w-6" />}
          tone="amber"
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader title="Recaudación" subtitle="Pagos confirmados (últimos 30 días)" />
          <CardBody>
            {serie.length === 0 ? (
              <div className="flex h-64 items-center justify-center text-sm text-slate-400">Sin datos de ventas</div>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={serie} margin={{ left: -16, right: 8, top: 8 }}>
                  <defs>
                    <linearGradient id="g" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#0d9488" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#0d9488" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" vertical={false} />
                  <XAxis dataKey="periodo" tick={{ fontSize: 11, fill: "#94a3b8" }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: "#94a3b8" }} tickLine={false} axisLine={false} />
                  <Tooltip
                    formatter={(v: any) => formatMoney(v)}
                    contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 13 }}
                  />
                  <Area type="monotone" dataKey="monto" stroke="#0d9488" strokeWidth={2} fill="url(#g)" />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Órdenes por estado" />
          <CardBody>
            {estados.length === 0 ? (
              <div className="flex h-64 items-center justify-center text-sm text-slate-400">Sin órdenes</div>
            ) : (
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie data={estados} dataKey="value" nameKey="name" innerRadius={55} outerRadius={85} paddingAngle={2}>
                    {estados.map((e) => (
                      <Cell key={e.name} fill={ESTADO_COLORS[e.name] ?? "#94a3b8"} />
                    ))}
                  </Pie>
                  <Legend iconType="circle" wrapperStyle={{ fontSize: 12 }} />
                  <Tooltip contentStyle={{ borderRadius: 12, border: "1px solid #e2e8f0", fontSize: 13 }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardBody>
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <MiniKpi icon={<Navigation className="h-5 w-5" />} label="Con tracking hoy" value={oper?.asignaciones_con_ping_hoy} />
        <MiniKpi icon={<Boxes className="h-5 w-5" />} label="Geocercas activas" value={oper?.geocercas_activas} />
        <MiniKpi icon={<Truck className="h-5 w-5" />} label="Vehículos operativos" value={kpi.vehiculos_por_estado?.Operativo} />
        <MiniKpi icon={<ShieldAlert className="h-5 w-5" />} label="Incidencias graves" value={kpi.incidencias_severidad_alta} tone="text-rose-600" />
      </div>

      <Card className="mt-6">
        <CardHeader title="Top clientes" subtitle="Por recaudación confirmada" />
        <DataTable
          rows={top}
          rowKey={(r) => r.cliente_id}
          columns={[
            { header: "Cliente", cell: (r) => <span className="font-medium text-slate-800">{r.nombre}</span> },
            { header: "Email", cell: (r) => <span className="text-slate-500">{r.email}</span> },
            { header: "Órdenes", align: "right", cell: (r) => formatNumber(r.ordenes) },
            { header: "Recaudado", align: "right", cell: (r) => <span className="font-semibold">{formatMoney(r.recaudado)}</span> },
          ]}
          empty="Aún no hay recaudación registrada"
        />
      </Card>
    </div>
  );
}

function MiniKpi({ icon, label, value, tone }: { icon: React.ReactNode; label: string; value?: number; tone?: string }) {
  return (
    <div className="card flex items-center gap-3 p-4">
      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-100 text-slate-500">{icon}</div>
      <div>
        <p className={`text-lg font-bold ${tone ?? "text-slate-900"}`}>{formatNumber(value ?? 0)}</p>
        <p className="text-xs text-slate-500">{label}</p>
      </div>
    </div>
  );
}
