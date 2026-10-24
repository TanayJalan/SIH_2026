import type { Config } from "tailwindcss";

/**
 * Design tokens for the AICTE approval workflow.
 *
 * Colours are declared as CSS variables in `src/index.css` so that the same
 * values are available to CSS, SVG and Radix portals. Spacing stays on
 * Tailwind's 4px base scale (1 = 0.25rem).
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          DEFAULT: "var(--ink)",
          700: "var(--ink-700)",
          500: "var(--ink-500)",
          300: "var(--ink-300)",
          100: "var(--ink-100)",
        },
        paper: "var(--paper)",
        surface: "var(--surface)",
        line: "var(--line)",
        saffron: {
          DEFAULT: "var(--saffron)",
          hover: "var(--saffron-hover)",
          strong: "var(--saffron-strong)",
          50: "var(--saffron-50)",
          100: "var(--saffron-100)",
          200: "var(--saffron-200)",
          300: "var(--saffron-300)",
          400: "var(--saffron-400)",
          500: "var(--saffron)",
          600: "var(--saffron-600)",
          700: "var(--saffron-700)",
        },
        ok: {
          DEFAULT: "var(--ok)",
          soft: "var(--ok-soft)",
          strong: "var(--ok-strong)",
          band: "var(--ok-band)",
        },
        watch: {
          DEFAULT: "var(--watch)",
          soft: "var(--watch-soft)",
          strong: "var(--watch-strong)",
          band: "var(--watch-band)",
        },
        breach: {
          DEFAULT: "var(--breach)",
          soft: "var(--breach-soft)",
          strong: "var(--breach-strong)",
          band: "var(--breach-band)",
        },
        info: {
          DEFAULT: "var(--info)",
          soft: "var(--info-soft)",
          strong: "var(--info-strong)",
          band: "var(--info-band)",
        },
        neutral: {
          DEFAULT: "var(--neutral)",
          soft: "var(--neutral-soft)",
          strong: "var(--neutral-strong)",
        },
        overlay: "var(--overlay)",
        focus: "var(--focus)",
        // Legacy aliases keep the existing application shell readable while
        // product screens are migrated to the new design system.
        navy: {
          950: "var(--ink)",
          900: "var(--ink)",
          800: "var(--ink-700)",
          700: "var(--ink-700)",
        },
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', "ui-sans-serif", "system-ui", "sans-serif"],
        serif: ['"Source Serif 4"', "ui-serif", "Georgia", "serif"],
      },
      fontSize: {
        12: ["0.75rem", { lineHeight: "1rem" }],
        13: ["0.8125rem", { lineHeight: "1.125rem" }],
        14: ["0.875rem", { lineHeight: "1.25rem" }],
        16: ["1rem", { lineHeight: "1.5rem" }],
        20: ["1.25rem", { lineHeight: "1.75rem" }],
        28: ["1.75rem", { lineHeight: "2.125rem" }],
        40: ["2.5rem", { lineHeight: "2.875rem" }],
      },
      borderRadius: {
        input: "var(--radius-input)",
        panel: "var(--radius-panel)",
        pill: "var(--radius-pill)",
      },
      boxShadow: {
        popover: "var(--shadow-popover)",
      },
    },
  },
} satisfies Config;
