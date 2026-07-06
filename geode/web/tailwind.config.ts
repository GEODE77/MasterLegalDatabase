import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        graphite: {
          0: "var(--graphite-0)",
          1: "var(--graphite-1)",
          2: "var(--graphite-2)",
          3: "var(--graphite-3)",
          4: "var(--graphite-4)",
          5: "var(--graphite-5)",
          6: "var(--graphite-6)",
          7: "var(--graphite-7)",
          8: "var(--graphite-8)",
          9: "var(--graphite-9)"
        },
        accent: {
          cyanotype: "var(--accent-cyanotype)",
          amber: "var(--accent-amber)"
        },
        signal: {
          success: "var(--signal-success)",
          warn: "var(--signal-warn)",
          error: "var(--signal-error)"
        }
      },
      fontFamily: {
        sans: ["var(--font-sans)", "Inter", "system-ui", "sans-serif"],
        mono: ["var(--font-mono)", "JetBrains Mono", "monospace"]
      },
      fontSize: {
        "2xs": "var(--text-2xs)",
        xs: "var(--text-xs)",
        sm: "var(--text-sm)",
        base: "var(--text-base)",
        md: "var(--text-md)",
        lg: "var(--text-lg)",
        xl: "var(--text-xl)",
        "2xl": "var(--text-2xl)",
        "3xl": "var(--text-3xl)"
      },
      spacing: {
        0: "var(--space-0)",
        1: "var(--space-1)",
        2: "var(--space-2)",
        3: "var(--space-3)",
        4: "var(--space-4)",
        5: "var(--space-5)",
        6: "var(--space-6)",
        8: "var(--space-8)",
        10: "var(--space-10)",
        12: "var(--space-12)"
      },
      borderRadius: {
        0: "var(--radius-0)",
        1: "var(--radius-1)",
        2: "var(--radius-2)",
        3: "var(--radius-3)",
        4: "var(--radius-4)"
      },
      boxShadow: {
        0: "var(--elevation-0)",
        1: "var(--elevation-1)",
        2: "var(--elevation-2)",
        3: "var(--elevation-3)"
      },
      transitionDuration: {
        1: "var(--dur-1)",
        2: "var(--dur-2)",
        3: "var(--dur-3)",
        4: "var(--dur-4)"
      },
      transitionTimingFunction: {
        mech: "var(--ease-mech)",
        snap: "var(--ease-snap)",
        linear: "var(--ease-linear)"
      }
    }
  }
};

export default config;
