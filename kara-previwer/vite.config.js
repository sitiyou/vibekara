import { defineConfig } from "vite";
import tailwind from "@tailwindcss/vite";
import { fileURLToPath } from "node:url";
const local = (path) => fileURLToPath(new URL(path, import.meta.url));
export default defineConfig({
  root: "frontend",
  base: "./",
  plugins: [tailwind()],
  esbuild: { jsx: "automatic" },
  resolve: {
    alias: {
      "@": local("./frontend"),
    },
  },
  build: {
    outDir: local("./kara_previwer/web"),
    assetsDir: "ui",
    emptyOutDir: true,
  },
});
