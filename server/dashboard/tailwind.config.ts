import type { Config } from "tailwindcss";

const config = {
  darkMode: ["class"],
  content: [
    "./pages/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./app/**/*.{ts,tsx}",
    "./src/**/*.{ts,tsx}",
  ],
  // Optimize for production builds
  future: {
    hoverOnlyWhenSupported: true,
  },
  experimental: {
    optimizeUniversalDefaults: true,
  },
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      spacing: {
        "2.5": "0.625rem",
      },
      fontFamily: {
        sans: ["Inter", "system-ui"],
        serif: ["ui-serif", "Georgia"],
        mono: ["Monaco", "Consolas", '"Courier New"', "monospace"],
        "inter-display": ["var(--font-inter)", "sans-serif"], // Now uses same as Inter
        inter: ["var(--font-inter)", "sans-serif"],
        roboto: ["var(--font-roboto-mono)", "sans-serif"],
        fustat: ["var(--font-fustat, ui-sans-serif)", "sans-serif"],
        "dm-mono": ["var(--font-dm-mono, ui-monospace)", "monospace"],
      },
      colors: {
        onSurface: {
          primary: "hsla(var(--onSurface-primary))",
          tertiary: "hsla(var(--onSurface-tertiary))",
          secondary: "hsla(var(--onSurface-secondary))",
          default: {
            primary: "var(--on-surface-default-primary)",
            secondary: "var(--on-surface-default-secondary)",
            tertiary: "var(--on-surface-default-tertiary)",
            brand: "var(--on-surface-default-brand)",
            "brand-hover": "var(--on-surface-default-brand-hover)",
          },
          event: {
            add: "var(--on-surface-event-add)",
            search: "var(--on-surface-event-search)",
            delete: "var(--on-surface-event-delete)",
            get: "var(--on-surface-event-get)",
          },
          positive: {
            primary: "var(--on-surface-positive-primary)",
            secondary: "var(--on-surface-positive-secondary)",
          },
          danger: {
            primary: "var(--on-surface-danger-primary)",
            secondary: "var(--on-surface-danger-secondary)",
          },
          info: {
            primary: "var(--on-surface-info-primary)",
            secondary: "var(--on-surface-info-secondary)",
          },
        },
        surface: {
          primary: "hsla(var(--surface-primary))",
          secondary: "hsla(var(--surface-secondary))",
          tertiary: "hsla(var(--surface-tertiary))",
          default: {
            primary: "var(--surface-default-primary)",
            "primary-hover": "var(--surface-default-primary-hover)",
            secondary: "var(--surface-default-secondary)",
            "secondary-hover": "var(--surface-default-secondary-hover)",
            "fg-secondary": "var(--surface-default-fg-secondary)",
            "fg-secondary-hover": "var(--surface-default-fg-secondary-hover)",
            tertiary: "var(--surface-default-tertiary)",
            "tertiary-hover": "var(--surface-default-tertiary-hover)",
            brand: "var(--surface-default-brand)",
            "brand-hover": "var(--surface-default-brand-hover)",
          },
          event: {
            add: "var(--surface-event-add)",
            search: "var(--surface-event-search)",
            delete: "var(--surface-event-delete)",
            get: "var(--surface-event-get)",
          },
          positive: {
            primary: "var(--surface-positive-primary)",
            "primary-hover": "var(--surface-positive-primary-hover)",
          },
          danger: {
            primary: "var(--surface-danger-primary)",
            "primary-hover": "var(--surface-danger-primary-hover)",
          },
          info: {
            primary: "var(--surface-info-primary)",
            "primary-hover": "var(--surface-info-primary-hover)",
          },
        },
        elevationLight: {
          "2": "hsla(var(--elevation-light-2))",
        },
        neutral: {
          "0": "hsl(var(--neutral-0))",
          "50": "hsl(var(--neutral-50))",
          "100": "hsl(var(--neutral-100))",
          "200": "hsl(var(--neutral-200))",
          "300": "hsl(var(--neutral-300))",
          "400": "hsl(var(--neutral-400))",
          "500": "hsl(var(--neutral-500))",
          "600": "hsl(var(--neutral-600))",
          "700": "hsl(var(--neutral-700))",
          "800": "hsl(var(--neutral-800))",
          "900": "hsl(var(--neutral-900))",
          "950": "hsl(var(--neutral-950))",
        },
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
          border: "var(--border-primary)",
          borderLight: "rgba(39, 39, 42, 1)",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        memoindigo: {
          DEFAULT: "hsla(244, 96%, 90%, 1)",
          strong: "hsl(244deg 54.62% 77.69%)",
          light: "hsla(244, 96%, 90%, 0.2)",
          medium: "hsla(244, 96%, 90%, 0.5)",
          foreground: "hsl(243.14deg 71.07% 52.55%)",
        },
        memoblue: {
          DEFAULT: "hsla(191, 100%, 88%, 1)",
          strong: "hsl(191.72deg 100% 82.94%)",
          light: "hsla(191, 100%, 88%, 0.3)",
          medium: "hsla(191, 100%, 88%, 0.5)",
          foreground: "hsl(191.61deg 100% 27.42%)",
        },
        memogreen: {
          DEFAULT: "hsla(76, 100%, 82%, 1)",
          strong: "hsl(76.48deg 79.17% 71.1%)",
          light: "hsla(76, 100%, 82%, 0.3)",
          medium: "hsla(76, 100%, 82%, 0.5)",
          foreground: "hsl(76deg 100% 20.59%)",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        sidebar: {
          DEFAULT: "hsl(var(--sidebar-background))",
          foreground: "hsl(var(--sidebar-foreground))",
          primary: "hsl(var(--sidebar-primary))",
          "primary-foreground": "hsl(var(--sidebar-primary-foreground))",
          accent: "hsl(var(--sidebar-accent))",
          "accent-foreground": "hsl(var(--sidebar-accent-foreground))",
          border: "hsl(var(--sidebar-border))",
          ring: "hsl(var(--sidebar-ring))",
        },
        memNeutral: {
          50: "var(--mem-neutral-50)",
          100: "var(--mem-neutral-100)",
          150: "var(--mem-neutral-150)",
          200: "var(--mem-neutral-200)",
          300: "var(--mem-neutral-300)",
          400: "var(--mem-neutral-400)",
          450: "var(--mem-neutral-450)",
          500: "var(--mem-neutral-500)",
          550: "var(--mem-neutral-550)",
          600: "var(--mem-neutral-600)",
          700: "var(--mem-neutral-700)",
          800: "var(--mem-neutral-800)",
          850: "var(--mem-neutral-850)",
          900: "var(--mem-neutral-900)",
          950: "var(--mem-neutral-950)",
        },
        memPurple: {
          50: "var(--mem-purple-50)",
          100: "var(--mem-purple-100)",
          150: "var(--mem-purple-150)",
          200: "var(--mem-purple-200)",
          300: "var(--mem-purple-300)",
          400: "var(--mem-purple-400)",
          500: "var(--mem-purple-500)",
          600: "var(--mem-purple-600)",
          700: "var(--mem-purple-700)",
          800: "var(--mem-purple-800)",
          900: "var(--mem-purple-900)",
          950: "var(--mem-purple-950)",
        },
        memGold: {
          50: "var(--mem-gold-50)",
          100: "var(--mem-gold-100)",
          150: "var(--mem-gold-150)",
          200: "var(--mem-gold-200)",
          300: "var(--mem-gold-300)",
          400: "var(--mem-gold-400)",
          500: "var(--mem-gold-500)",
          600: "var(--mem-gold-600)",
          700: "var(--mem-gold-700)",
          800: "var(--mem-gold-800)",
          900: "var(--mem-gold-900)",
          950: "var(--mem-gold-950)",
        },
        memBlue: {
          50: "var(--mem-blue-50)",
          100: "var(--mem-blue-100)",
          200: "var(--mem-blue-200)",
          300: "var(--mem-blue-300)",
          400: "var(--mem-blue-400)",
          500: "var(--mem-blue-500)",
          600: "var(--mem-blue-600)",
          700: "var(--mem-blue-700)",
          800: "var(--mem-blue-800)",
          900: "var(--mem-blue-900)",
          950: "var(--mem-blue-950)",
        },
        memGreen: {
          50: "var(--mem-green-50)",
          100: "var(--mem-green-100)",
          200: "var(--mem-green-200)",
          300: "var(--mem-green-300)",
          400: "var(--mem-green-400)",
          500: "var(--mem-green-500)",
          600: "var(--mem-green-600)",
          700: "var(--mem-green-700)",
          800: "var(--mem-green-800)",
          900: "var(--mem-green-900)",
          950: "var(--mem-green-950)",
        },
        memRed: {
          50: "var(--mem-red-50)",
          100: "var(--mem-red-100)",
          200: "var(--mem-red-200)",
          300: "var(--mem-red-300)",
          400: "var(--mem-red-400)",
          500: "var(--mem-red-500)",
          600: "var(--mem-red-600)",
          700: "var(--mem-red-700)",
          800: "var(--mem-red-800)",
          900: "var(--mem-red-900)",
          950: "var(--mem-red-950)",
        },
        memBorder: {
          primary: "var(--mem-border-primary)",
          secondary: "var(--mem-border-secondary)",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      boxShadow: {
        custom: "0px 3px 10px 0px rgba(0, 0, 0, 0.08)",
      },
      keyframes: {
        "accordion-down": {
          from: {
            height: "0",
          },
          to: {
            height: "var(--radix-accordion-content-height)",
          },
        },
        "accordion-up": {
          from: {
            height: "var(--radix-accordion-content-height)",
          },
          to: {
            height: "0",
          },
        },
        "fade-in": {
          "0%": {
            opacity: "0",
          },
          "100%": {
            opacity: "1",
          },
        },
        "fade-in-right": {
          "0%": {
            opacity: "0",
            transform: "translateX(-5%)",
          },
          "100%": {
            opacity: "1",
            transform: "translateX(0)",
          },
        },
        shimmer: {
          "0%": {
            transform: "translateX(-100%)",
          },
          "100%": {
            transform: "translateX(100%)",
          },
        },
        "shimmer-subtle": {
          "0%": { backgroundPosition: "-100% 0" },
          "100%": { backgroundPosition: "100% 0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "fade-in": "fade-in 0.3s ease-in-out",
        "fade-in-right": "fade-in-right 0.5s ease-out",
        shimmer: "shimmer 2s ease-in-out infinite",
        "shimmer-subtle": "shimmer-subtle 1.5s linear infinite",
      },
    },
  },
  plugins: [require("tailwindcss-animate"), require("@tailwindcss/typography")],
} satisfies Config;

export default config;
