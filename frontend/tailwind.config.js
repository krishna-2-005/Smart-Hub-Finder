/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter Variable"', "system-ui", "-apple-system", '"Segoe UI"', "sans-serif"],
      },
      colors: {
        brand: {
          50: "#eef4ff",
          100: "#dbe7fe",
          200: "#bfd3fe",
          300: "#93b4fd",
          400: "#6090fa",
          500: "#3b6ef6",
          600: "#2552eb",
          700: "#1d3fd8",
          800: "#1e35af",
          900: "#1e328a",
          950: "#172054",
        },
        ink: {
          DEFAULT: "#0f172a",
          secondary: "#475569",
          muted: "#64748b",
        },
      },
      boxShadow: {
        card: "0 1px 2px rgba(15, 23, 42, 0.04), 0 1px 3px rgba(15, 23, 42, 0.06)",
        pop: "0 10px 30px -10px rgba(15, 23, 42, 0.25)",
      },
    },
  },
  plugins: [],
};
