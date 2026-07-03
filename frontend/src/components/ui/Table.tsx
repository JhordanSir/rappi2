import type { ReactNode } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { Spinner } from "./Feedback";

export interface Column<T> {
  header: ReactNode;
  cell: (row: T) => ReactNode;
  className?: string;
  align?: "left" | "right" | "center";
  /** Campo de ordenamiento server-side (parámetro `orden_por`). Si se define y la
   *  tabla recibe `onSort`, la cabecera se vuelve clicable (estilo Excel). */
  sortKey?: string;
}

export interface SortState {
  key: string;
  dir: "asc" | "desc";
}

/** Alterna el sort de una columna: sin orden → asc → desc → sin orden. Úsalo en las
 *  páginas para mantener el patrón consistente. */
export function toggleSort(actual: SortState | null, key: string): SortState | null {
  if (actual?.key !== key) return { key, dir: "asc" };
  if (actual.dir === "asc") return { key, dir: "desc" };
  return null;
}

export function DataTable<T>({
  columns,
  rows,
  rowKey,
  loading,
  empty,
  onRowClick,
  footer,
  sort,
  onSort,
}: {
  columns: Column<T>[];
  rows: T[] | undefined;
  rowKey: (row: T) => string | number;
  loading?: boolean;
  empty?: ReactNode;
  onRowClick?: (row: T) => void;
  /** Pie de tabla, p. ej. controles de paginación. */
  footer?: ReactNode;
  /** Orden activo (server-side) para pintar el indicador en la cabecera. */
  sort?: SortState | null;
  /** Clic en una cabecera ordenable; la página decide (normalmente `toggleSort`). */
  onSort?: (key: string) => void;
}) {
  return (
    <div>
      <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-left">
            {columns.map((c, i) => {
              const sortable = !!c.sortKey && !!onSort;
              const activo = sortable && sort?.key === c.sortKey;
              return (
                <th
                  key={i}
                  onClick={sortable ? () => onSort!(c.sortKey!) : undefined}
                  title={sortable ? "Ordenar por esta columna" : undefined}
                  className={cn(
                    "whitespace-nowrap px-4 py-3 text-xs font-semibold uppercase tracking-wide text-slate-500",
                    c.align === "right" && "text-right",
                    c.align === "center" && "text-center",
                    sortable && "cursor-pointer select-none hover:text-slate-700",
                    activo && "text-brand-700",
                    c.className,
                  )}
                >
                  <span className={cn("inline-flex items-center gap-1", c.align === "right" && "flex-row-reverse")}>
                    {c.header}
                    {sortable && (
                      activo ? (
                        sort!.dir === "asc" ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />
                      ) : (
                        <ArrowUpDown className="h-3 w-3 opacity-40" />
                      )
                    )}
                  </span>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-16">
                <div className="flex justify-center">
                  <Spinner />
                </div>
              </td>
            </tr>
          ) : !rows || rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="px-4 py-12 text-center text-sm text-slate-400">
                {empty ?? "Sin registros"}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr
                key={rowKey(row)}
                onClick={() => onRowClick?.(row)}
                className={cn(
                  "border-b border-slate-100 transition last:border-0",
                  onRowClick && "cursor-pointer hover:bg-slate-50",
                )}
              >
                {columns.map((c, i) => (
                  <td
                    key={i}
                    className={cn(
                      "px-4 py-3 text-slate-700",
                      c.align === "right" && "text-right",
                      c.align === "center" && "text-center",
                      c.className,
                    )}
                  >
                    {c.cell(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
      </div>
      {footer}
    </div>
  );
}
