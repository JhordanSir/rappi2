import { describe, expect, it } from "vitest";
import { toCSV } from "./csv";

describe("toCSV", () => {
  it("genera cabecera desde las claves de la primera fila", () => {
    const csv = toCSV([{ periodo: "2026-07-01", monto: 120.5 }]);
    expect(csv.split("\r\n")[0]).toBe("periodo,monto");
    expect(csv.split("\r\n")[1]).toBe("2026-07-01,120.5");
  });

  it("escapa comas, comillas y saltos de línea (RFC 4180)", () => {
    const csv = toCSV([{ nombre: 'Juan "Chato", Pérez', nota: "línea1\nlínea2" }]);
    const linea = csv.split("\r\n")[1];
    expect(linea).toBe('"Juan ""Chato"", Pérez","línea1\nlínea2"');
  });

  it("null/undefined quedan como celdas vacías", () => {
    const csv = toCSV([{ a: null, b: undefined, c: 0 }]);
    expect(csv.split("\r\n")[1]).toBe(",,0");
  });

  it("sin filas devuelve cadena vacía", () => {
    expect(toCSV([])).toBe("");
  });

  it("respeta el orden de columnas explícito", () => {
    const csv = toCSV([{ a: 1, b: 2 }], ["b", "a"]);
    expect(csv.split("\r\n")[0]).toBe("b,a");
    expect(csv.split("\r\n")[1]).toBe("2,1");
  });
});
