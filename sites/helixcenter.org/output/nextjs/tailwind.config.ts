import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        helix: {
          dark: "#1a1a2e",
          navy: "#16213e",
          blue: "#0f3460",
          accent: "#e94560",
          gold: "#c4a35a",
          cream: "#f5f0e8",
        },
      },
      fontFamily: {
        serif: ["Georgia", "Times New Roman", "serif"],
        sans: ["Helvetica Neue", "Arial", "sans-serif"],
      },
      typography: {
        DEFAULT: {
          css: {
            maxWidth: "none",
            color: "#333",
            a: {
              color: "#0f3460",
              "&:hover": {
                color: "#e94560",
              },
            },
          },
        },
      },
    },
  },
  plugins: [],
};

export default config;
