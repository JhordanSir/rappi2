import { describe, expect, it } from "vitest";
import { tienePermiso } from "./permisos";

describe("tienePermiso (permisos con comodín)", () => {
  const admin = [{ recurso: "*", accion: "*" }];
  const soloLectura = [{ recurso: "ordenes", accion: "read" }];
  const porRecurso = [{ recurso: "usuarios", accion: "*" }];

  it("el comodín total concede cualquier cosa", () => {
    expect(tienePermiso(admin, "usuarios", "delete")).toBe(true);
    expect(tienePermiso(admin, "lo-que-sea", "write")).toBe(true);
  });

  it("permiso exacto concede solo esa combinación", () => {
    expect(tienePermiso(soloLectura, "ordenes", "read")).toBe(true);
    expect(tienePermiso(soloLectura, "ordenes", "write")).toBe(false);
    expect(tienePermiso(soloLectura, "usuarios", "read")).toBe(false);
  });

  it("comodín por recurso concede todas las acciones del recurso", () => {
    expect(tienePermiso(porRecurso, "usuarios", "delete")).toBe(true);
    expect(tienePermiso(porRecurso, "ordenes", "read")).toBe(false);
  });

  it("sin permisos (o undefined) no concede nada", () => {
    expect(tienePermiso([], "ordenes", "read")).toBe(false);
    expect(tienePermiso(undefined, "ordenes", "read")).toBe(false);
  });
});
