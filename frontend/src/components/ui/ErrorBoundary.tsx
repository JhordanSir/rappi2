import { Component } from "react";
import type { ErrorInfo, ReactNode } from "react";
import { RefreshCw, TriangleAlert } from "lucide-react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

/** Última línea de defensa ante errores de render no manejados: en vez de una
 *  pantalla en blanco, muestra un mensaje amigable con la opción de recargar.
 *  (Los errores de red/API NO llegan aquí: los maneja el onError global de
 *  react-query en lib/queryClient.ts con un toast.) */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Log local para diagnóstico (visible en la consola del navegador).
    console.error("ErrorBoundary:", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="flex min-h-screen items-center justify-center bg-sillar-100 px-6">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-card">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-rose-100">
            <TriangleAlert className="h-6 w-6 text-rose-500" />
          </div>
          <h1 className="mt-4 text-lg font-bold text-slate-900">Algo salió mal</h1>
          <p className="mt-2 text-sm text-slate-500">
            Ocurrió un error inesperado en la aplicación. Recárgala para continuar; si el
            problema persiste, contacta al administrador.
          </p>
          <button
            onClick={() => window.location.reload()}
            className="mt-6 inline-flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-brand-700"
          >
            <RefreshCw className="h-4 w-4" /> Recargar la aplicación
          </button>
        </div>
      </div>
    );
  }
}
