/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        cream: { 50: "#FDFBF7", 100: "#FAF6EE", 200: "#F2EBDD" },
        saffron: { 400: "#F6B73C", 500: "#EFA21A", 600: "#D98A0B" },
        tangerine: { 400: "#F58A4B", 500: "#EC6F2A", 600: "#D4571A" },
        night: { 800: "#17211D", 900: "#0F1613" },
      },
      fontFamily: {
        display: ['"Bricolage Grotesque"', "ui-sans-serif", "system-ui", "sans-serif"],
        sans: ["Figtree", "ui-sans-serif", "system-ui", "sans-serif"],
      },
      boxShadow: { soft: "0 1px 2px rgba(20,40,30,.04), 0 8px 24px -12px rgba(20,60,40,.14)" },
    },
  },
  plugins: [],
};
