import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // Branded primary; Tailwind v3 picks up CSS vars set by the layout.
        brand: {
          DEFAULT: "rgb(var(--brand-primary) / <alpha-value>)",
          fg: "rgb(var(--brand-foreground) / <alpha-value>)",
        },
      },
    },
  },
  plugins: [],
};

export default config;
