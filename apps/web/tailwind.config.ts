import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./app/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        canvas: "hsl(var(--bg-canvas))",
        surface: "hsl(var(--bg-surface))",
        "surface-2": "hsl(var(--bg-surface-2))",
        accent: "hsl(var(--accent))",
        pos: "hsl(var(--pos))",
        neg: "hsl(var(--neg))",
        info: "hsl(var(--info))",
        primary: "hsl(var(--text-primary))",
        secondary: "hsl(var(--text-secondary))",
        tertiary: "hsl(var(--text-tertiary))",
        border: {
          subtle: "hsl(var(--border-subtle))",
          strong: "hsl(var(--border-strong))"
        },
        factor: {
          momentum: "#5AC8FA",
          value: "#2DD4BF",
          quality: "#A78BFA",
          "low-vol": "#FCD34D",
          size: "#F472B6",
          composite: "#94A3B8"
        }
      },
      fontFamily: {
        sans: ["var(--font-inter)"],
        mono: ["var(--font-jetbrains-mono)"]
      }
    }
  },
  plugins: []
};

export default config;
