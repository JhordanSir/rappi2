import type { ReactNode } from "react";
import { Modal } from "./Modal";
import { Button } from "./Button";

export type DetailRow = { label: string; value: ReactNode; full?: boolean };

/**
 * Modal de solo lectura para ver la ficha completa de un registro.
 * Renderiza una lista de filas etiqueta/valor; `full` ocupa el ancho completo.
 * Reutilizable desde los listados (botón "ojo") de cualquier entidad.
 */
export function DetailModal({
  open,
  onClose,
  title,
  description,
  rows,
  size = "md",
  children,
}: {
  open: boolean;
  onClose: () => void;
  title?: ReactNode;
  description?: ReactNode;
  rows: DetailRow[];
  size?: "sm" | "md" | "lg" | "xl";
  children?: ReactNode;
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      description={description}
      size={size}
      footer={<Button variant="outline" onClick={onClose}>Cerrar</Button>}
    >
      <dl className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
        {rows.map((r, i) => (
          <div key={i} className={r.full ? "sm:col-span-2" : undefined}>
            <dt className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">{r.label}</dt>
            <dd className="mt-0.5 text-sm text-slate-800">{r.value === null || r.value === undefined || r.value === "" ? "—" : r.value}</dd>
          </div>
        ))}
      </dl>
      {children}
    </Modal>
  );
}
