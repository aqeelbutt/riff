import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { transformSync } from "esbuild";
import path from "node:path";

export default defineConfig({
  plugins: [
    // Components in this app are .js files containing JSX (Next's default). Vite only treats .jsx/.tsx as JSX,
    // so without this any test that imports a component dies with "content contains invalid JS syntax".
    {
      name: "riff:jsx-in-js",
      enforce: "pre",
      transform(code, id) {
        if (!/\/src\/.*\.js$/.test(id) || !/<[A-Za-z/]/.test(code)) return null;
        return transformSync(code, { loader: "jsx", jsx: "automatic", sourcefile: id, sourcemap: true });
      },
    },
    react(),
  ],
  test: { environment: "jsdom", globals: true, setupFiles: ["./vitest.setup.js"], include: ["src/**/*.test.{js,jsx}"] },
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
});
