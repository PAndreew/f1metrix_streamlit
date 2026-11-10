import { defineConfig } from "vite";

export default defineConfig({
  // Prebundle the lazy worker dependency up front. Discovering it on the first
  // explorer visit otherwise reloads the page and loses the user's search.
  optimizeDeps: { include: ["chart.js", "sql.js"] },
});
