/** Riff design tokens (from the approved mocks): dark studio, coral accent, mint = ready, violet = Claude/lyrics. */
module.exports = {
  content: ["./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: "var(--bg)", "bg-2": "var(--bg-2)", sur: "var(--sur)", "sur-2": "var(--sur-2)", "sur-3": "var(--sur-3)",
        line: "var(--line)", "line-2": "var(--line-2)", ink: "var(--ink)", "ink-2": "var(--ink-2)", "ink-3": "var(--ink-3)",
        acc: "var(--acc)", "acc-2": "var(--acc-2)", mint: "var(--mint)", vio: "var(--vio)", amber: "var(--amber)",
      },
      fontFamily: { disp: ["Bricolage Grotesque", "IBM Plex Sans", "sans-serif"], sans: ["IBM Plex Sans", "sans-serif"], mono: ["IBM Plex Mono", "monospace"] },
      borderRadius: { r: "12px", "r-sm": "8px" },
    },
  },
  plugins: [],
};
