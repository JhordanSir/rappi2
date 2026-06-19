import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "./Button";

export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
}: {
  /** Página actual (base 0). */
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : page * pageSize + 1;
  const to = Math.min(total, (page + 1) * pageSize);

  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 px-4 py-3 text-sm text-slate-500">
      <span>
        {total === 0 ? (
          "Sin registros"
        ) : (
          <>
            Mostrando <b className="text-slate-700">{from}–{to}</b> de{" "}
            <b className="text-slate-700">{total}</b>
          </>
        )}
      </span>
      <div className="flex items-center gap-2">
        <Button size="sm" variant="outline" disabled={page <= 0} onClick={() => onPageChange(page - 1)}>
          <ChevronLeft className="h-4 w-4" /> Anterior
        </Button>
        <span className="tabular-nums text-slate-600">
          Página {page + 1} de {pages}
        </span>
        <Button size="sm" variant="outline" disabled={page >= pages - 1} onClick={() => onPageChange(page + 1)}>
          Siguiente <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}
