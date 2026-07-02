import path from "path";
import { defineConfig } from "vitest/config";

// Config de tests separada de vite.config.ts (mismo alias "@" → src). Sin el plugin
// de react: esbuild ya transforma TSX (tsconfig jsx: react-jsx) y el plugin del build
// (vite 5) no es compatible con el vite interno de vitest 4.
export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/setupTests.ts"],
  },
});
