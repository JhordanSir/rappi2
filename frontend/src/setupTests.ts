// Matchers de jest-dom (toBeInTheDocument, etc.) registrados sobre expect de vitest.
import "@testing-library/jest-dom/vitest";
import { afterEach } from "vitest";
import { cleanup } from "@testing-library/react";

// Sin `globals: true`, testing-library no registra su auto-cleanup: desmontar entre
// tests evita duplicados ("Found multiple elements").
afterEach(cleanup);
