/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Primario: teal del gopher (Rapi2)
        brand: {
          50: "#f0fdfa",
          100: "#ccfbf1",
          200: "#99f6e4",
          300: "#5eead4",
          400: "#2dd4bf",
          500: "#14b8a6",
          600: "#0d9488",
          700: "#0f766e",
          800: "#115e59",
          900: "#134e4a",
          950: "#042f2e",
        },
        // Acento: ámbar (scooter / sol arequipeño)
        sun: {
          50: "#fffbeb",
          100: "#fef3c7",
          200: "#fde68a",
          300: "#fcd34d",
          400: "#fbbf24",
          500: "#f59e0b",
          600: "#d97706",
          700: "#b45309",
          800: "#92400e",
          900: "#78350f",
        },
        // Sillar: cremas cálidos de la Ciudad Blanca
        sillar: {
          50: "#fbf9f5",
          100: "#f5f0e8",
          200: "#ece3d4",
          300: "#e0d3bc",
          400: "#cdb999",
        },
        // Piedra volcánica para el sidebar
        ink: {
          900: "#1b1916",
          800: "#262420",
          700: "#34302a",
          600: "#46413a",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px 0 rgba(28,24,18,.06), 0 1px 3px 0 rgba(28,24,18,.1)",
        soft: "0 8px 30px -10px rgba(28,24,18,.22)",
      },
      keyframes: {
        "fade-in": { from: { opacity: 0, transform: "translateY(4px)" }, to: { opacity: 1, transform: "translateY(0)" } },
      },
      animation: {
        "fade-in": "fade-in .18s ease-out",
      },
    },
  },
  plugins: [],
};
