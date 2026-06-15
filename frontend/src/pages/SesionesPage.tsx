import { MonitorSmartphone, ShieldX, LogOut } from "lucide-react";
import toast from "react-hot-toast";
import { api, apiError } from "@/lib/api";
import { useSesiones, useApiMutation } from "@/api/hooks";
import { useAuth } from "@/auth/AuthContext";
import { PageHeader } from "@/components/ui/PageHeader";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { DataTable } from "@/components/ui/Table";
import { Badge } from "@/components/ui/Badge";
import { formatDate } from "@/lib/utils";

export default function SesionesPage() {
  const { user } = useAuth();
  const { data, isLoading } = useSesiones({ activos_solo: true });
  const revocar = useApiMutation((sid: number) => api.delete(`/usuarios/${user!.id}/sesiones/${sid}`), ["sesiones"]);
  const revocarTodas = useApiMutation(() => api.delete(`/usuarios/${user!.id}/sesiones`), ["sesiones"]);

  return (
    <div>
      <PageHeader
        title="Mis sesiones"
        subtitle="Dispositivos con sesión activa (refresh tokens). Revoca los que no reconozcas."
        actions={
          <Button
            variant="danger"
            onClick={() => revocarTodas.mutate(undefined as any, { onSuccess: () => toast.success("Todas las sesiones revocadas"), onError: (e) => toast.error(apiError(e)) })}
            loading={revocarTodas.isPending}
          >
            <LogOut className="h-4 w-4" /> Cerrar todas
          </Button>
        }
      />
      <Card>
        <DataTable
          rows={data}
          loading={isLoading}
          rowKey={(s) => s.id}
          empty="No hay sesiones activas"
          columns={[
            { header: "Sesión", cell: (s) => <span className="inline-flex items-center gap-2 font-medium text-stone-800"><MonitorSmartphone className="h-4 w-4 text-stone-400" /> #{s.id}</span> },
            { header: "Expira", cell: (s) => <span className="text-stone-500">{formatDate(s.fecha_expiracion)}</span> },
            { header: "Estado", cell: (s) => <Badge tone={s.revocado ? "gray" : "green"}>{s.revocado ? "Revocada" : "Activa"}</Badge> },
            {
              header: "",
              align: "right",
              cell: (s) =>
                !s.revocado && (
                  <Button size="sm" variant="outline" className="text-rose-600" onClick={() => revocar.mutate(s.id, { onSuccess: () => toast.success("Sesión revocada"), onError: (e) => toast.error(apiError(e)) })}>
                    <ShieldX className="h-3.5 w-3.5" /> Revocar
                  </Button>
                ),
            },
          ]}
        />
      </Card>
    </div>
  );
}
