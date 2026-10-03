// Servidor estático Node.js: publica HTML, CSS, JavaScript e configuração pública do Gateway.

// Importa o servidor HTTP nativo do Node.js, sem instalar um framework adicional.
import http from "node:http";

// Importa leitura assíncrona dos arquivos estáticos do frontend.
import { readFile } from "node:fs/promises";

// Converte a URL deste módulo em um caminho de arquivo local.
import { fileURLToPath } from "node:url";

// Importa utilitários para resolver caminhos e extensões de arquivos.
import path from "node:path";

// Obtém a pasta deste módulo Node.js para servir os arquivos corretos.
const raiz = path.dirname(fileURLToPath(import.meta.url));

// Restringe o servidor aos quatro caminhos públicos conhecidos do frontend.
const arquivos = {

  // Fornece o valor textual ou a configuração deste campo.
  "/": "index.html",

  // Fornece o valor textual ou a configuração deste campo.
  "/index.html": "index.html",

  // Fornece o valor textual ou a configuração deste campo.
  "/app.js": "app.js",

  // Fornece o valor textual ou a configuração deste campo.
  "/style.css": "style.css",

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
};

// Relaciona extensões de arquivo ao Content-Type enviado ao navegador.
const tipos = {

  // Fornece o valor textual ou a configuração deste campo.
  ".html": "text/html; charset=utf-8",

  // Fornece o valor textual ou a configuração deste campo.
  ".js": "text/javascript; charset=utf-8",

  // Fornece o valor textual ou a configuração deste campo.
  ".css": "text/css; charset=utf-8",

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
};

// Usa a porta configurada no ambiente ou 8080 como padrão.
const porta = Number(process.env.FRONTEND_PORT || 8080);

// Usa o módulo HTTP nativo para preparar o servidor do frontend.
http

  // Define o callback assíncrono executado a cada requisição HTTP recebida pelo servidor.
  .createServer(async (req, res) => {

    // Interpreta o caminho pedido pelo navegador sem depender dos parâmetros da URL.
    const url = new URL(req.url, "http://localhost");

    // Trata a configuração pública do Gateway como um script JavaScript gerado pelo servidor.
    if (url.pathname === "/config.js") {

      // Envia os headers de uma resposta bem-sucedida antes do conteúdo.
      res.writeHead(200, {

        // Informa o formato e a codificação do corpo HTTP ao navegador ou servidor.
        "Content-Type": "text/javascript; charset=utf-8",

        // Impede reutilizar uma resposta antiga de configuração ou de arquivo durante a demonstração.
        "Cache-Control": "no-store",

      // Fecha o bloco, callback, chamada ou coleção iniciado acima.
      });

      // Envia o conteúdo da resposta e finaliza a requisição HTTP.
      res.end(

        // Gera somente a URL pública do Gateway; JSON.stringify escapa o valor dentro do script.
        `window.API_URL=${JSON.stringify(process.env.GATEWAY_PUBLIC_URL || "http://localhost:8000")};`,

      // Fecha o bloco, callback, chamada ou coleção iniciado acima.
      );

      // Encerra este callback porque não há outra ação válida nesta situação.
      return;

    // Fecha o bloco, callback, chamada ou coleção iniciado acima.
    }

    // Resolve o caminho solicitado pela lista de arquivos permitidos.
    const arquivo = arquivos[url.pathname];

    // Recusa caminhos que não foram explicitamente liberados para o servidor estático.
    if (!arquivo) {

      // Responde 404 para caminhos fora da lista de arquivos permitidos.
      res.writeHead(404);

      // Envia o conteúdo da resposta e finaliza a requisição HTTP.
      res.end("Não encontrado");

      // Encerra este callback porque não há outra ação válida nesta situação.
      return;

    // Fecha o bloco, callback, chamada ou coleção iniciado acima.
    }

    // Executa a operação protegida pelo tratamento de erros abaixo.
    try {

      // Lê o arquivo estático que será enviado como resposta HTTP.
      const corpo = await readFile(path.join(raiz, arquivo));

      // Envia os headers de uma resposta bem-sucedida antes do conteúdo.
      res.writeHead(200, {

        // Informa o formato e a codificação do corpo HTTP ao navegador ou servidor.
        "Content-Type": tipos[path.extname(arquivo)],

        // Impede reutilizar uma resposta antiga de configuração ou de arquivo durante a demonstração.
        "Cache-Control": "no-store",

      // Fecha o bloco, callback, chamada ou coleção iniciado acima.
      });

      // Envia o conteúdo da resposta e finaliza a requisição HTTP.
      res.end(corpo);

    // Trata a falha sem apresentá-la como sucesso ao usuário.
    } catch {

      // Responde 500 quando falha a leitura de um arquivo do frontend.
      res.writeHead(500);

      // Envia o conteúdo da resposta e finaliza a requisição HTTP.
      res.end("Falha ao carregar a página");

    // Fecha o bloco, callback, chamada ou coleção iniciado acima.
    }

  // Fecha o bloco, callback, chamada ou coleção iniciado acima.
  })

  // Define o callback que transforma ou processa o elemento atual da coleção.
  .listen(porta, "0.0.0.0", () =>

    // Mostra a URL local da loja no log depois que o servidor inicia.
    console.log(`Loja: http://localhost:${porta}`),

  // Fecha o bloco, callback, chamada ou coleção iniciado acima.
  );
