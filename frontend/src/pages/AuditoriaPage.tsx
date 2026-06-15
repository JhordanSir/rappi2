import { useState } from "react";
import { Activity, ServerCrash, Globe, Clock } from "lucide-react";
import { useAuditoria, useAuditoriaResumen } from "@/api/hooks";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card, CardHeader } from "@/components/ui/Card";
import { StatCard } from "@/components/ui/StatCard";
import { DataTable } from "@/components/ui/Table";
import { Badge } from "@/components/ui/Badge";
import { Select } from "@/components/ui/Field";
import { Toolbar } from "@/components/ui/Toolbar";
import { formatDate, formatNumber } from "@/lib/utils";

const METODOS = ["GET", "POST", "PATCH", "PUT", "DELETE"];

function statusTone(code: number) {
  if (code >= 500) return "red";
  if (code >= 400) return "amber";
  if (code >= 300) return "indigo";
  return "green";
}

export default function AuditoriaPage() {
  const [metodo, setMetodo] = useState("");
  const [horas, setHoras] = useState(24);
  const { data: logs, isLoading } = useAuditoria({ limit: 200, ...(metodo ? { metodo } : {}) });
  const { data: resumen } = useAuditoriaResumen({ horas });

  const total = resumen?.total_requests ?? resumen?.total ?? 0;
  const errores = resumen?.errores_4xx_5xx ?? resumen?.errores ?? 0;
  const byMetodo: Record<string, number> = resumen?.by_metodo ?? resumen?.por_metodo ?? {};

  return (
    <div>
      <PageHeader title="Auditoría" subtitle="Registro de todas las peticiones HTTP al API (MongoDB, TTL 90 días)" />

      <Toolbar>
        <Select value={String(horas)} onChange={(e) => setHoras(Number(e.target.value))} className="h-10 w-auto">
          {[6, 24, 72, 168, 720].map((h) => <option key={h} value={h}>Últimas {h}h</option>)}
        </Select>
        <Select value={metodo} onChange={(e) => setMetodo(e.target.value)} className="h-10 w-auto">
          <option value="">Todos los métodos</option>
          {METODOS.map((m) => <option key={m} value={m}>{m}</option>)}
        </Select>
      </Toolbar>

      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard label={`Peticiones (${horas}h)`} value={formatNumber(total)} icon={<Activity className="h-6 w-6" />} tone="brand" />
        <StatCard label="Errores 4xx/5xx" value={formatNumber(errores)} icon={<ServerCrash className="h-6 w-6" />} tone="red" />
        <StatCard label="Métodos distintos" value={formatNumber(Object.keys(byMetodo).length)} icon={<Globe className="h-6 w-6" />} tone="indigo" />
        <StatCard label="Ventana" value={`${horas} h`} icon={<Clock className="h-6 w-6" />} tone="amber" />
      </div>

      <Card>
        <CardHeader title="Eventos recientes" />
        <DataTable
          rows={logs}
          loading={isLoading}
          rowKey={(l) => l.id}
          empty="Sin eventos de auditoría"
          columns={[
            { header: "Método", cell: (l) => <Badge tone="slate">{l.metodo}</Badge> },
            { header: "Ruta", cell: (l) => <span className="font-mono text-xs text-stone-600">{l.ruta}</span> },
            { header: "Status", cell: (l) => <Badge tone={statusTone(l.status_code) as any}>{l.status_code}</Badge> },
            { header: "Usuario", cell: (l) => (l.usuario_id ? `#${l.usuario_id}` : <span className="text-stone-400">anónimo</span>) },
            { header: "IP", cell: (l) => <span className="font-mono text-xs text-stone-500">{l.ip || "—"}</span> },
            { header: "Fecha", cell: (l) => <span className="text-stone-500">{formatDate(l.timestamp)}</span> },
          ]}
        />
      </Card>
    </div>
  );
}
