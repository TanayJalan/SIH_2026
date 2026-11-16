import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath, URL } from "node:url";
import { defineConfig, loadEnv, type Plugin } from "vite";

/**
 * Inline the single stylesheet into index.html. The shell has no meaningful
 * markup before React mounts, so removing the render-blocking CSS request lets
 * the first paint happen one round trip earlier on slow connections.
 *
 * The file stays on disk (as an empty stylesheet) because route chunks list it
 * in their preload dependency map; deleting it would make those chunks fail to
 * load. The styles themselves are already in the document.
 */
function inlineStylesheet(): Plugin {
  return {
    name: "aicte-inline-stylesheet",
    apply: "build",
    enforce: "post",
    closeBundle() {
      const htmlPath = join(process.cwd(), "dist", "index.html");
      let html = readFileSync(htmlPath, "utf8");
      const link = html.match(/<link rel="stylesheet"[^>]*href="\/([^"]+\.css)"[^>]*>/);
      if (!link) {
        return;
      }
      const cssPath = join(process.cwd(), "dist", link[1]);
      const css = readFileSync(cssPath, "utf8");
      html = html.replace(link[0], `<style>${css}</style>`);
      writeFileSync(htmlPath, html);
      writeFileSync(cssPath, "/* Inlined into index.html. */\n");
    },
  };
}

/**
 * Connect to the API origin while the shell and route chunk are still
 * downloading. The SPA always calls the API cross-origin, so this removes one
 * DNS + TCP + TLS handshake from the first request.
 */
function apiPreconnect(apiUrl: string): Plugin {
  let origin: string | null = null;
  try {
    origin = new URL(apiUrl).origin;
  } catch {
    origin = null;
  }
  return {
    name: "aicte-api-preconnect",
    transformIndexHtml(html) {
      if (!origin) {
        return html;
      }
      return {
        html,
        tags: [
          {
            tag: "link",
            attrs: { rel: "preconnect", href: origin, crossorigin: "" },
            injectTo: "head-prepend",
          },
          {
            tag: "link",
            attrs: { rel: "dns-prefetch", href: origin },
            injectTo: "head-prepend",
          },
        ],
      };
    },
  };
}

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  return {
    plugins: [
      react(),
      tailwindcss(),
      apiPreconnect(env.VITE_API_URL || "http://localhost:8000"),
      inlineStylesheet(),
    ],
    resolve: {
      alias: {
        "@": fileURLToPath(new URL("./src", import.meta.url)),
      },
    },
    server: {
      host: "0.0.0.0",
      port: 5173,
      strictPort: true,
    },
  };
});
