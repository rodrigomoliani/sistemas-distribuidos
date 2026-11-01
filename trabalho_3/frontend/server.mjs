import http from "node:http";
import { readFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import path from "node:path";

const raiz = path.dirname(fileURLToPath(import.meta.url));

const arquivos = {
  "/": "index.html",
  "/index.html": "index.html",
  "/app.js": "app.js",
  "/style.css": "style.css",
};

const tipos = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
};

const porta = Number(process.env.FRONTEND_PORT || 8080);

http
  .createServer(async (req, res) => {
    const url = new URL(req.url, "http://localhost");

    // Injeta dinamicamente a URL pública do API Gateway
    if (url.pathname === "/config.js") {
      res.writeHead(200, {
        "Content-Type": "text/javascript; charset=utf-8",
        "Cache-Control": "no-store",
      });
      res.end(
        `window.API_URL=${JSON.stringify(process.env.GATEWAY_PUBLIC_URL || "http://localhost:8000")};`
      );
      return;
    }

    const arquivo = arquivos[url.pathname];
    if (!arquivo) {
      res.writeHead(404);
      res.end("Não encontrado");
      return;
    }

    try {
      const corpo = await readFile(path.join(raiz, arquivo));
      res.writeHead(200, {
        "Content-Type": tipos[path.extname(arquivo)],
        "Cache-Control": "no-store",
      });
      res.end(corpo);
    } catch {
      res.writeHead(500);
      res.end("Falha ao carregar a página");
    }
  })
  .listen(porta, "0.0.0.0", () => {
    console.log(`Loja: http://localhost:${porta}`);
  });
