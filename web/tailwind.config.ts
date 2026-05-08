import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  safelist: [
    {
      pattern:
        /^(bg|text|border|ring)-state-(green|amber|red|blue|purple|rose)(-ink|-soft|-tint)?$/,
    },
    {
      pattern:
        /^(group-hover|group-focus-within):(text|bg)-state-(green|amber|red|blue|purple|rose)(-ink|-soft|-tint)?$/,
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
        mono: [
          "JetBrains Mono",
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },
      fontSize: {
        "hero": ["5rem", { lineHeight: "1", letterSpacing: "-0.04em" }],
        "score": ["3rem", { lineHeight: "1", letterSpacing: "-0.03em" }],
      },
      colors: {
        ink: {
          DEFAULT: "#0f172a",
          muted: "#475569",
          subtle: "#94a3b8",
          faint: "#cbd5e1",
        },
        paper: {
          DEFAULT: "#ffffff",
          tinted: "#f8fafc",
          divider: "#e2e8f0",
        },
        state: {
          green: {
            DEFAULT: "#16a34a",
            ink: "#166534",
            soft: "#dcfce7",
            tint: "#f0fdf4",
          },
          amber: {
            DEFAULT: "#d97706",
            ink: "#92400e",
            soft: "#fef3c7",
            tint: "#fffbeb",
          },
          red: {
            DEFAULT: "#dc2626",
            ink: "#991b1b",
            soft: "#fee2e2",
            tint: "#fef2f2",
          },
          blue: {
            DEFAULT: "#2563eb",
            ink: "#1e40af",
            soft: "#dbeafe",
            tint: "#eff6ff",
          },
          purple: {
            DEFAULT: "#7c3aed",
            ink: "#5b21b6",
            soft: "#ede9fe",
            tint: "#f5f3ff",
          },
          rose: {
            DEFAULT: "#e11d48",
            ink: "#9f1239",
            soft: "#ffe4e6",
            tint: "#fff1f2",
          },
        },
      },
      transitionTimingFunction: {
        linear: "cubic-bezier(0.32, 0.72, 0, 1)",
      },
    },
  },
  plugins: [],
};

export default config;
