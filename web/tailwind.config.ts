import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  safelist: [
    {
      pattern:
        /^(bg|text|border|ring|stroke|fill|from|to|via)-state-(green|amber|red|blue|purple|rose)(-ink|-soft|-tint)?$/,
    },
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        // Editorial display — Newsreader is variable, optical, with italic
        display: [
          "Newsreader",
          "ui-serif",
          "Georgia",
          "Times New Roman",
          "serif",
        ],
        mono: [
          "IBM Plex Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },
      fontSize: {
        // Hero score — set in Newsreader, light weight, with optical sizing
        hero: ["6.5rem", { lineHeight: "0.92", letterSpacing: "-0.04em" }],
        // Chapter / section headings
        chapter: ["1.625rem", { lineHeight: "1.1", letterSpacing: "-0.015em" }],
        // Ring center number
        ring: ["2.5rem", { lineHeight: "1", letterSpacing: "-0.025em" }],
        // Card-level emphasized number
        card: ["1.875rem", { lineHeight: "1", letterSpacing: "-0.02em" }],
      },
      colors: {
        // warm paper-ink palette
        ink: {
          DEFAULT: "#16140f", // near-black with warm undertone — like ink on paper
          muted: "#5a554b", // body / secondary
          subtle: "#8a8474", // tertiary
          faint: "#b4ad9a", // quaternary, for hairlines
        },
        paper: {
          DEFAULT: "#ffffff", // card surface
          tinted: "#fbfaf7", // page background — warm off-white
          divider: "#e5e1d8", // hairlines / borders
          elevated: "#fdfcf9", // hover surface
        },
        // state colors — bright DEFAULT for ring fills (signal), deeper ink for text
        state: {
          green: {
            DEFAULT: "#10b981", // emerald-500 — ring fill / signal
            ink: "#15803d", // emerald-700 — editorial label
            soft: "#d1fae5", // emerald-100 — pill bg
            tint: "#ecfdf5", // emerald-50
          },
          amber: {
            DEFAULT: "#f59e0b",
            ink: "#9a3412", // burnt sienna ink
            soft: "#fef3c7",
            tint: "#fffbeb",
          },
          red: {
            DEFAULT: "#ef4444",
            ink: "#991b1b", // oxblood
            soft: "#fee2e2",
            tint: "#fef2f2",
          },
          blue: {
            DEFAULT: "#0ea5e9",
            ink: "#1e3a8a", // deep cobalt
            soft: "#dbeafe",
            tint: "#eff6ff",
          },
          purple: {
            DEFAULT: "#8b5cf6",
            ink: "#5b21b6",
            soft: "#ede9fe",
            tint: "#f5f3ff",
          },
          rose: {
            DEFAULT: "#f43f5e",
            ink: "#9f1239",
            soft: "#ffe4e6",
            tint: "#fff1f2",
          },
        },
      },
      borderRadius: {
        // tighter radii — document-like, not app-like
        DEFAULT: "3px",
        md: "4px",
        lg: "6px",
        xl: "8px",
      },
      transitionTimingFunction: {
        linear: "cubic-bezier(0.32, 0.72, 0, 1)",
      },
      boxShadow: {
        // very restrained — single hairline, almost no elevation
        card: "0 1px 0 rgba(22, 20, 15, 0.04)",
        "card-hover": "0 1px 0 rgba(22, 20, 15, 0.08)",
      },
    },
  },
  plugins: [],
};

export default config;
