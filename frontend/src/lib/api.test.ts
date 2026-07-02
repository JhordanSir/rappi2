import { describe, expect, it } from "vitest";
import { apiError } from "./api";

// apiError extrae mensajes legibles de las respuestas de error de FastAPI.
describe("apiError", () => {
  it("detail string se devuelve tal cual", () => {
    const err = { response: { data: { detail: "Conductor no disponible" } } };
    expect(apiError(err)).toBe("Conductor no disponible");
  });

  it("detail de validación (array 422) se aplana campo: mensaje", () => {
    const err = {
      response: {
        data: {
          detail: [
            { loc: ["body", "largo_cm"], msg: "debe ser mayor que 0" },
            { loc: ["body", "email"], msg: "formato inválido" },
          ],
        },
      },
    };
    expect(apiError(err)).toBe("largo_cm: debe ser mayor que 0 · email: formato inválido");
  });

  it("sin detail cae al message del error", () => {
    expect(apiError({ message: "Network Error" })).toBe("Network Error");
  });

  it("sin nada devuelve un mensaje genérico", () => {
    expect(apiError({})).toBe("Ocurrió un error inesperado");
  });
});
