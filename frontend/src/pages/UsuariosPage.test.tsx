import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

const mutateMock = vi.fn();

vi.mock("@/auth/AuthContext", () => ({
  useAuth: () => ({ can: () => true, user: null, loading: false, login: vi.fn(), logout: vi.fn() }),
}));

vi.mock("@/lib/api", () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  apiError: (e: unknown) => String(e),
}));

vi.mock("@/api/hooks", () => ({
  usePaginated: () => ({
    data: {
      items: [
        { id: 1, username: "activo1", email: "a@x.com", activo: true, rol_id: 1, fecha_registro: "2026-01-01T00:00:00Z", rol: { id: 1, nombre: "Admin", permisos: [] } },
        { id: 2, username: "inactivo1", email: "b@x.com", activo: false, rol_id: 2, fecha_registro: "2026-01-01T00:00:00Z", rol: { id: 2, nombre: "Cliente", permisos: [] } },
      ],
      total: 2,
    },
    isLoading: false,
  }),
  useRoles: () => ({ data: [{ id: 1, nombre: "Admin" }, { id: 2, nombre: "Cliente" }] }),
  useDebouncedValue: (v: string) => v,
  useApiMutation: () => ({ mutate: mutateMock, isPending: false, variables: undefined }),
}));

import UsuariosPage from "./UsuariosPage";

describe("UsuariosPage (usuarios deshabilitados)", () => {
  it("muestra activos e inactivos con su badge de estado", () => {
    render(<UsuariosPage />);
    expect(screen.getByText("activo1")).toBeInTheDocument();
    expect(screen.getByText("inactivo1")).toBeInTheDocument();
    expect(screen.getByText("Inactivo")).toBeInTheDocument();
  });

  it("tiene el filtro de estado (Todos / Activos / Inactivos)", () => {
    render(<UsuariosPage />);
    expect(screen.getByText("Todos los estados")).toBeInTheDocument();
    expect(screen.getByText("Solo inactivos")).toBeInTheDocument();
  });

  it("la fila inactiva ofrece Reactivar (no Desactivar) y dispara la mutación", () => {
    render(<UsuariosPage />);
    const reactivar = screen.getByTitle("Reactivar");
    expect(reactivar).toBeInTheDocument();
    fireEvent.click(reactivar);
    expect(mutateMock).toHaveBeenCalledWith(2, expect.anything());
  });
});
