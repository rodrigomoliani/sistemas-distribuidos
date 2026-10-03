// Interface JavaScript: comandos REST e acompanhamento de pedidos por SSE.

// Ativa verificações mais rigorosas do JavaScript para evitar atribuições acidentais.
"use strict";

// Guarda o endereço público do Gateway recebido em config.js.
const API = window.API_URL;

// Cria um atalho para selecionar um elemento do documento por seu seletor CSS.
const $ = (s) => document.querySelector(s);

// Restaura o UUID do navegador para manter os pedidos da mesma sessão.
let cliente = localStorage.getItem("campus.cliente");

// Verifica esta condição antes de aplicar a atualização ou continuar o fluxo.
if (!cliente) {

  // Gera um UUID para este navegador quando ainda não existe identificador salvo.
  cliente = crypto.randomUUID();

  // Persiste o identificador ou nome no navegador para reutilizá-lo após recarregar a loja.
  localStorage.setItem("campus.cliente", cliente);

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
}

// Inicializa a lista de produtos consultados no Estoque.
let produtos = [],

  // Mantém as quantidades da sacola, indexadas pelo ID do produto.
  carrinho = {},

  // Mantém o filtro atual; texto vazio seleciona todas as categorias.
  categoria = "",

  // Mantém os pedidos carregados para o cliente deste navegador.
  pedidos = [],

  // Guarda a Promise da consulta em andamento para coordenar atualizações concorrentes.
  atualizacaoPedidos = null,

  // Sinaliza que outra atualização chegou durante a consulta em andamento.
  atualizarNovamente = false,

  // Indica uma criação de pedido em andamento para impedir envios repetidos.
  pendente = false;

// Formata centavos como moeda brasileira, convertendo para reais apenas na apresentação.
const dinheiro = (n) =>

  // Configura a formatação de moeda em português do Brasil.
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(

    // Converte centavos inteiros em reais somente para exibir a moeda.
    n / 100,

  // Fecha o bloco, callback, chamada ou coleção iniciado acima.
  );

// Relaciona as categorias A, B e C aos nomes exibidos na loja.
const categorias = { A: "Papelaria", B: "Vestuário", C: "Eletrônicos" };

// Define as descrições curtas dos três produtos do catálogo.
const nomes = {

  // Define a descrição curta do produto identificado por este número.
  1: "Para todas as suas ideias.",

  // Define a descrição curta do produto identificado por este número.
  2: "Conforto para qualquer dia.",

  // Define a descrição curta do produto identificado por este número.
  3: "Sua trilha sonora, por perto.",

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
};

// Escapa caracteres especiais antes de inserir dados em HTML, evitando interpretar texto como marcação.
const escapar = (s) =>

  // Converte valores ausentes em texto vazio antes de escapar a saída HTML.
  String(s ?? "").replace(

    // Localiza os caracteres que poderiam alterar a interpretação do HTML.
    /[&<>"']/g,

    // Define o callback que transforma ou processa o elemento atual da coleção.
    (c) =>

      // Substitui cada caractere especial pela entidade HTML correspondente.
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[

        // Usa o caractere encontrado como chave do mapa de entidades HTML.
        c

      // Fecha o bloco, callback, chamada ou coleção iniciado acima.
      ],

  // Fecha o bloco, callback, chamada ou coleção iniciado acima.
  );

// Define ilustrações SVG locais para representar as categorias sem baixar imagens externas.
const artes = {

  // Define a ilustração ou o nome desta categoria do catálogo.
  A: (

    // Inicia uma ilustração vetorial local, ignorada pelo leitor de tela.
    "<svg viewBox=\"0 0 130 150\" aria-hidden=\"true\">" +

    // Agrupa e transforma as formas da ilustração.
    "<g transform=\"rotate(-10 65 75)\">" +

    // Desenha uma forma retangular da ilustração.
    "<rect x=\"29\" y=\"22\" width=\"79\" height=\"111\" rx=\"3\" fill=\"#cbd8b6\"/>" +

    // Desenha uma forma retangular da ilustração.
    "<rect x=\"23\" y=\"18\" width=\"79\" height=\"111\" rx=\"3\" fill=\"#aabd95\"/>" +

    // Desenha o contorno vetorial usando os pontos definidos.
    "<path d=\"M32 18v111\" stroke=\"#7e986a\"/>" +

    // Insere o texto decorativo dentro da ilustração.
    "<text x=\"44\" y=\"60\" font-family=\"sans-serif\" font-weight=\"bold\" font-size=\"12\" fill=\"#365639\">GOOD</text>" +

    // Insere o texto decorativo dentro da ilustração.
    "<text x=\"44\" y=\"75\" font-family=\"sans-serif\" font-weight=\"bold\" font-size=\"12\" fill=\"#365639\">IDEAS</text>" +

    // Insere o texto decorativo dentro da ilustração.
    "<text x=\"44\" y=\"90\" font-family=\"sans-serif\" font-weight=\"bold\" font-size=\"12\" fill=\"#365639\">START</text>" +

    // Insere o texto decorativo dentro da ilustração.
    "<text x=\"44\" y=\"105\" font-family=\"sans-serif\" font-weight=\"bold\" font-size=\"12\" fill=\"#365639\">HERE.</text>" +

    // Fecha o elemento HTML aberto no trecho anterior.
    "</g>" +

    // Fecha o elemento HTML aberto no trecho anterior.
    "</svg>"

  // Fecha o bloco, callback, chamada ou coleção iniciado acima.
  ),

  // Define a ilustração ou o nome desta categoria do catálogo.
  B: (

    // Inicia uma ilustração vetorial local, ignorada pelo leitor de tela.
    "<svg viewBox=\"0 0 150 150\" aria-hidden=\"true\">" +

    // Desenha o contorno vetorial usando os pontos definidos.
    "<path d=\"M51 28L28 39 10 67l24 13 13-17v62h58V63l13 17 24-13-18-28-23-11c-7 10-13 13-25 13S58 38 51 28\" fill=\"#c6b899\"/>" +

    // Desenha o contorno vetorial usando os pontos definidos.
    "<path d=\"M51 28c3 15 14 20 25 20s22-5 25-20\" fill=\"none\" stroke=\"#ab9a78\" stroke-width=\"3\"/>" +

    // Insere o texto decorativo dentro da ilustração.
    "<text x=\"61\" y=\"83\" font-size=\"10\" font-family=\"sans-serif\" fill=\"#6f654e\">campus</text>" +

    // Fecha o elemento HTML aberto no trecho anterior.
    "</svg>"

  // Fecha o bloco, callback, chamada ou coleção iniciado acima.
  ),

  // Define a ilustração ou o nome desta categoria do catálogo.
  C: (

    // Inicia uma ilustração vetorial local, ignorada pelo leitor de tela.
    "<svg viewBox=\"0 0 150 150\" aria-hidden=\"true\">" +

    // Desenha o contorno vetorial usando os pontos definidos.
    "<path d=\"M33 87V67c0-55 85-55 85 0v20\" fill=\"none\" stroke=\"#344851\" stroke-width=\"14\"/>" +

    // Desenha o contorno vetorial usando os pontos definidos.
    "<path d=\"M34 76V64c0-47 82-47 82 0v12\" fill=\"none\" stroke=\"#667a83\" stroke-width=\"4\"/>" +

    // Desenha uma forma retangular da ilustração.
    "<rect x=\"22\" y=\"70\" width=\"25\" height=\"48\" rx=\"10\" fill=\"#344851\"/>" +

    // Desenha uma forma retangular da ilustração.
    "<rect x=\"105\" y=\"70\" width=\"25\" height=\"48\" rx=\"10\" fill=\"#344851\"/>" +

    // Desenha uma forma retangular da ilustração.
    "<rect x=\"38\" y=\"76\" width=\"15\" height=\"40\" rx=\"7\" fill=\"#63777f\"/>" +

    // Desenha uma forma retangular da ilustração.
    "<rect x=\"99\" y=\"76\" width=\"15\" height=\"40\" rx=\"7\" fill=\"#63777f\"/>" +

    // Fecha o elemento HTML aberto no trecho anterior.
    "</svg>"

  // Fecha o bloco, callback, chamada ou coleção iniciado acima.
  ),

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
};

// Envia uma requisição REST ao Gateway, interpreta JSON e transforma respostas de erro em mensagens.
async function api(caminho, opcoes = {}) {

  // Guarda a resposta HTTP para conferir o status e interpretar seu corpo.
  const r = await fetch(API + caminho, {

    // Reutiliza as opções e headers fornecidos pelo chamador sem perder o formato JSON padrão.
    ...opcoes,

    // Informa o formato e a codificação do corpo HTTP ao navegador ou servidor.
    headers: { "Content-Type": "application/json", ...opcoes.headers },

  // Fecha o bloco, callback, chamada ou coleção iniciado acima.
  });

  // Interpreta os dados JSON da resposta HTTP ou da notificação SSE.
  const d = await r.json();

  // Confere se o servidor respondeu com erro antes de considerar a operação concluída.
  if (!r.ok)

    // Transforma a condição de falha em mensagem para o tratamento de erro da interface.
    throw new Error(

      // Usa o detalhe textual do servidor quando disponível; caso contrário mostra uma orientação geral.
      typeof d.detail === "string"

        // Fornece o detalhe de erro devolvido pela API ao usuário.
        ? d.detail

        // Completa esta expressão com os argumentos ou valores utilizados na etapa api.
        : "Confira os dados e tente novamente.",

    // Fecha o bloco, callback, chamada ou coleção iniciado acima.
    );

  // Devolve os dados JSON apenas depois de verificar que a resposta HTTP foi bem-sucedida.
  return d;

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
}

// Guarda o temporizador do aviso para substituí-lo quando uma nova mensagem chegar.
let toastTimer;

// Exibe feedback temporário e troca a aparência quando a mensagem representa um erro.
function aviso(texto, erro = false) {

  // Seleciona o elemento da página que receberá esta atualização.
  const el = $("#mensagem");

  // Atualiza o texto visível sem interpretar conteúdo recebido como HTML.
  el.textContent = texto;

  // Aplica a aparência de erro somente quando o aviso representa uma falha.
  el.classList.toggle("erro", erro);

  // Torna a área de feedback visível para o usuário.
  el.hidden = false;

  // Cancela o aviso anterior para que seu temporizador não esconda a nova mensagem.
  clearTimeout(toastTimer);

  // Guarda o temporizador do aviso para substituí-lo quando uma nova mensagem chegar.
  toastTimer = setTimeout(() => (el.hidden = true), 6500);

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
}

// Monta os cartões do catálogo de acordo com a categoria selecionada.
function desenharProdutos() {

  // Mantém somente os produtos que atendem ao filtro de categoria.
  const filtrados = produtos.filter(

    // Aceita todos os produtos se o filtro estiver vazio, ou somente a categoria selecionada.
    (p) => !categoria || p.categoria === categoria,

  // Fecha o bloco, callback, chamada ou coleção iniciado acima.
  );

  // Substitui a marcação desta área pelos cartões ou pela orientação calculada.
  $("#produtos").innerHTML =

    // Completa esta expressão com os argumentos ou valores utilizados na etapa desenharProdutos.
    filtrados

      // Transforma cada registro em item ou trecho de interface sem alterar os dados originais.
      .map(

        // Define o callback que transforma ou processa o elemento atual da coleção.
        (p) =>

          // Completa esta expressão com os argumentos ou valores utilizados na etapa desenharProdutos.
          (

            // Define o cartão de produto ou pedido.
            `<article class="produto">` +

            // Agrupa visualmente os elementos desta parte do cartão.
            `<div class="produto-arte ${p.categoria}">` +

            // Mostra a etiqueta, o estado ou uma etapa da linha do tempo.
            `<span class="categoria-tag">${categorias[p.categoria]}</span>${artes[p.categoria]}</div>` +

            // Agrupa visualmente os elementos desta parte do cartão.
            `<div class="produto-info">` +

            // Exibe o nome do produto ou a identificação resumida do pedido.
            `<h3>${escapar(p.nome)}</h3>` +

            // Exibe descrição, saldo, nota fiscal ou orientação ao usuário.
            `<p class="produto-sub">${nomes[p.id] || ""} · ${p.quantidade} disponíveis</p>` +

            // Agrupa visualmente os elementos desta parte do cartão.
            `<div class="produto-preco">` +

            // Destaca o preço ou o nome nesta parte da interface.
            `<strong>${dinheiro(p.preco_centavos)}</strong>` +

            // Cria um controle com identificação e rótulo acessível para tratar o clique.
            `<button class="adicionar" data-produto="${escapar(p.id)}" aria-label="Adicionar ${escapar(p.nome)}" ${p.quantidade <= 0 ? "disabled" : ""}>+</button>` +

            // Fecha o elemento HTML aberto no trecho anterior.
            `</div>` +

            // Fecha o elemento HTML aberto no trecho anterior.
            `</div>` +

            // Fecha o elemento HTML aberto no trecho anterior.
            `</article>`

          // Fecha o bloco, callback, chamada ou coleção iniciado acima.
          ),

      // Fecha o bloco, callback, chamada ou coleção iniciado acima.
      )

      // Une os trechos gerados em uma única string HTML ou descrição de itens.
      .join("") ||

    // Exibe descrição, saldo, nota fiscal ou orientação ao usuário.
    '<p class="vazio sem-produtos">Nenhum produto disponível nesta categoria.</p>';

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
}

// Calcula quantidade e total em centavos e atualiza os controles da sacola.
function desenharCarrinho() {

  // Inicia ou atualiza o total da sacola em centavos.
  let total = 0,

    // Inicia ou atualiza a quantidade de unidades na sacola.
    quantidade = 0;

  // Converte os produtos da sacola em cartões HTML ou itens do corpo JSON.
  const itens = Object.entries(carrinho)

    // Define o callback que transforma ou processa o elemento atual da coleção.
    .map(([pid, q]) => {

      // Localiza o produto ou recebe o pedido devolvido pelo Gateway.
      const p = produtos.find((p) => p.id === pid);

      // Ignora um item cujo produto não está mais presente no catálogo carregado.
      if (!p) return "";

      // Acumula preço unitário em centavos multiplicado pela quantidade.
      total += q * p.preco_centavos;

      // Acumula o número total de unidades selecionadas.
      quantidade += q;

      // Completa esta expressão com os argumentos ou valores utilizados na etapa desenharCarrinho.
      return (

        // Agrupa visualmente os elementos desta parte do cartão.
        `<div class="sacola-item">` +

        // Agrupa visualmente os elementos desta parte do cartão.
        `<div>` +

        // Destaca o preço ou o nome nesta parte da interface.
        `<strong>${escapar(p.nome)}</strong>` +

        // Mostra a etiqueta, o estado ou uma etapa da linha do tempo.
        `<span>${dinheiro(p.preco_centavos)}</span>` +

        // Fecha o elemento HTML aberto no trecho anterior.
        `</div>` +

        // Agrupa visualmente os elementos desta parte do cartão.
        `<div class="contador">` +

        // Cria um controle com identificação e rótulo acessível para tratar o clique.
        `<button data-ajuste="-1" data-produto="${pid}" aria-label="Remover uma unidade de ${escapar(p.nome)}">−</button>` +

        // Mostra a etiqueta, o estado ou uma etapa da linha do tempo.
        `<span>${q}</span>` +

        // Cria um controle com identificação e rótulo acessível para tratar o clique.
        `<button data-ajuste="1" data-produto="${pid}" aria-label="Adicionar uma unidade de ${escapar(p.nome)}">+</button>` +

        // Fecha o elemento HTML aberto no trecho anterior.
        `</div>` +

        // Fecha o elemento HTML aberto no trecho anterior.
        `</div>`

      // Fecha o bloco, callback, chamada ou coleção iniciado acima.
      );

    // Fecha o bloco, callback, chamada ou coleção iniciado acima.
    })

    // Une os trechos gerados em uma única string HTML ou descrição de itens.
    .join("");

  // Substitui a marcação desta área pelos cartões ou pela orientação calculada.
  $("#itens-sacola").innerHTML =

    // Completa esta expressão com os argumentos ou valores utilizados na etapa desenharCarrinho.
    itens || '<p class="vazio">Escolha um produto para começar.</p>';

  // Atualiza o texto visível sem interpretar conteúdo recebido como HTML.
  $("#total").textContent = dinheiro(total);

  // Atualiza o texto visível sem interpretar conteúdo recebido como HTML.
  $("#quantidade-sacola").textContent = quantidade;

  // Bloqueia a finalização quando a sacola está vazia ou já há envio em andamento.
  $("#finalizar").disabled = quantidade === 0 || pendente;

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
}

// Consulta o estoque atual via Gateway e redesenha catálogo e sacola.
async function carregarProdutos() {

  // Executa a operação protegida pelo tratamento de erros abaixo.
  try {

    // Inicializa a lista de produtos consultados no Estoque.
    produtos = await api("/produtos");

    // Atualiza os cartões do catálogo com o filtro e os dados atuais.
    desenharProdutos();

    // Recalcula a sacola e a disponibilidade do botão de finalizar.
    desenharCarrinho();

  // Trata a falha sem apresentá-la como sucesso ao usuário.
  } catch (e) {

    // Substitui a marcação desta área pelos cartões ou pela orientação calculada.
    $("#produtos").innerHTML =

      // Exibe descrição, saldo, nota fiscal ou orientação ao usuário.
      '<p class="vazio sem-produtos">Não foi possível consultar o estoque. Use “Atualizar estoque” para tentar novamente.</p>';

    // Apresenta ao usuário o resultado ou a falha desta operação.
    aviso(e.message, true);

  // Fecha o bloco, callback, chamada ou coleção iniciado acima.
  }

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
}

// Completa esta expressão com os argumentos ou valores utilizados na etapa atual.
$("#atualizar").addEventListener("click", carregarProdutos);

// Define o callback que transforma ou processa o elemento atual da coleção.
document.querySelectorAll(".filtro").forEach((b) =>

  // Registra um callback para responder à interação ou à mensagem indicada.
  b.addEventListener("click", () => {

    // Mantém o filtro atual; texto vazio seleciona todas as categorias.
    categoria = b.dataset.categoria;

    // Seleciona no documento os controles que receberão os eventos.
    document

      // Seleciona todos os elementos que correspondem ao seletor CSS indicado.
      .querySelectorAll(".filtro")

      // Destaca apenas o botão de filtro que foi selecionado.
      .forEach((x) => x.classList.toggle("ativo", x === b));

    // Atualiza os cartões do catálogo com o filtro e os dados atuais.
    desenharProdutos();

  // Fecha o bloco, callback, chamada ou coleção iniciado acima.
  }),

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
);

// Registra um callback para responder à interação ou à mensagem indicada.
$("#produtos").addEventListener("click", (e) => {

  // Localiza o botão responsável pela interação atual.
  const b = e.target.closest("[data-produto]");

  // Ignora cliques em áreas que não correspondem ao botão esperado.
  if (!b) return;

  // Completa esta expressão com os argumentos ou valores utilizados na etapa atual.
  alterar(b.dataset.produto, 1);

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
});

// Registra um callback para responder à interação ou à mensagem indicada.
$("#itens-sacola").addEventListener("click", (e) => {

  // Localiza o botão responsável pela interação atual.
  const b = e.target.closest("[data-ajuste]");

  // Verifica esta condição antes de aplicar a atualização ou continuar o fluxo.
  if (b) alterar(b.dataset.produto, Number(b.dataset.ajuste));

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
});

// Ajusta a quantidade do produto na sacola respeitando o saldo exibido.
function alterar(pid, ajuste) {

  // Localiza o produto ou recebe o pedido devolvido pelo Gateway.
  const p = produtos.find((p) => p.id === pid);

  // Calcula a quantidade após somar o ajuste positivo ou negativo.
  const nova = (carrinho[pid] || 0) + ajuste;

  // Impede selecionar mais unidades do que o saldo mostrado no catálogo.
  if (nova > p.quantidade) {

    // Apresenta ao usuário o resultado ou a falha desta operação.
    aviso("Quantidade acima do estoque disponível.", true);

    // Encerra este callback porque não há outra ação válida nesta situação.
    return;

  // Fecha o bloco, callback, chamada ou coleção iniciado acima.
  }

  // Remove o produto da sacola quando sua quantidade chega a zero.
  if (nova <= 0) delete carrinho[pid];

  // Guarda a nova quantidade positiva do produto na sacola.
  else carrinho[pid] = nova;

  // Recalcula a sacola e a disponibilidade do botão de finalizar.
  desenharCarrinho();

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
}

// Completa esta expressão com os argumentos ou valores utilizados na etapa atual.
$("#nome").value = localStorage.getItem("campus.nome") || "";

// Registra um callback para responder à interação ou à mensagem indicada.
$("#pedido-form").addEventListener("submit", async (e) => {

  // Impede o envio tradicional do formulário e mantém a página aberta para usar REST.
  e.preventDefault();

  // Ignora uma nova submissão enquanto a anterior ainda está em processamento.
  if (pendente) return;

  // Indica uma criação de pedido em andamento para impedir envios repetidos.
  pendente = true;

  // Recalcula a sacola e a disponibilidade do botão de finalizar.
  desenharCarrinho();

  // Executa a operação protegida pelo tratamento de erros abaixo.
  try {

    // Lê o nome informado e remove espaços das extremidades.
    const nome = $("#nome").value.trim();

    // Transforma a condição de falha em mensagem para o tratamento de erro da interface.
    if (!nome) throw new Error("Informe seu nome.");

    // Persiste o identificador ou nome no navegador para reutilizá-lo após recarregar a loja.
    localStorage.setItem("campus.nome", nome);

    // Localiza o produto ou recebe o pedido devolvido pelo Gateway.
    const p = await api("/pedidos", {

      // Define o método HTTP adequado ao comando REST desta operação.
      method: "POST",

      // Serializa o corpo JSON com os dados necessários ao comando REST.
      body: JSON.stringify({

        // Inclui cliente no corpo JSON enviado ao Gateway.
        cliente,

        // Inclui nome no corpo JSON enviado ao Gateway.
        nome,

        // Converte cada par da sacola em item com ID e quantidade, sem enviar preços do navegador.
        itens: Object.entries(carrinho).map(([produto_id, quantidade]) => ({

          // Inclui produto_id no corpo JSON enviado ao Gateway.
          produto_id,

          // Inclui quantidade no corpo JSON enviado ao Gateway.
          quantidade,

        // Fecha o bloco, callback, chamada ou coleção iniciado acima.
        })),

      // Fecha o bloco, callback, chamada ou coleção iniciado acima.
      }),

    // Fecha o bloco, callback, chamada ou coleção iniciado acima.
    });

    // Mantém as quantidades da sacola, indexadas pelo ID do produto.
    carrinho = {};

    // Mostra imediatamente o novo pedido no início da lista.
    pedidos.unshift(p);

    // Atualiza o DOM com o estado e o histórico de pedidos disponíveis.
    desenharPedidos();

    // Apresenta ao usuário o resultado ou a falha desta operação.
    aviso("Pedido criado. Aguarde a confirmação do estoque para pagar.");

    // Leva a seção de acompanhamento para a tela após criar o pedido.
    $("#pedidos").scrollIntoView({ behavior: "smooth" });

    // Atualiza o saldo exibido depois de uma operação que pode alterar reservas.
    await carregarProdutos();

  // Trata a falha sem apresentá-la como sucesso ao usuário.
  } catch (e) {

    // Apresenta ao usuário o resultado ou a falha desta operação.
    aviso(e.message, true);

  // Restaura os controles mesmo quando a operação termina com erro.
  } finally {

    // Indica uma criação de pedido em andamento para impedir envios repetidos.
    pendente = false;

    // Recalcula a sacola e a disponibilidade do botão de finalizar.
    desenharCarrinho();

  // Fecha o bloco, callback, chamada ou coleção iniciado acima.
  }

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
});

// Monta o estado e a linha do tempo de cada pedido, com checkout e nota simulada.
function desenharPedidos() {

  // Seleciona o elemento da página que receberá esta atualização.
  const el = $("#lista-pedidos");

  // Mostra a orientação inicial quando ainda não há pedidos deste cliente.
  if (!pedidos.length) {

    // Substitui a marcação desta área pelos cartões ou pela orientação calculada.
    el.innerHTML =

      // Exibe descrição, saldo, nota fiscal ou orientação ao usuário.
      '<p class="vazio grande">Seus pedidos aparecerão aqui. Encontre seu próximo favorito no catálogo.</p>';

    // Encerra este callback porque não há outra ação válida nesta situação.
    return;

  // Fecha o bloco, callback, chamada ou coleção iniciado acima.
  }

  // Substitui a marcação desta área pelos cartões ou pela orientação calculada.
  el.innerHTML = pedidos

    // Define o callback que transforma ou processa o elemento atual da coleção.
    .map((p) => {

      // Identifica estados em que a interface não deve oferecer pagamento ou cancelamento.
      const encerrado = [

        // Inclui este estado no conjunto usado para decidir as ações ou a aparência do pedido.
        "Pedido Enviado",

        // Inclui este estado no conjunto usado para decidir as ações ou a aparência do pedido.
        "Pagamento Aprovado",

        // Inclui este estado no conjunto usado para decidir as ações ou a aparência do pedido.
        "Pagamento Recusado",

        // Inclui este estado no conjunto usado para decidir as ações ou a aparência do pedido.
        "Estoque Indisponível",

        // Inclui este estado no conjunto usado para decidir as ações ou a aparência do pedido.
        "Pedido Cancelado",

      // Confere se o estado do pedido pertence ao conjunto definido acima.
      ].includes(p.estado);

      // Identifica recusas, indisponibilidade e cancelamento para destacar o status.
      const erro = [

        // Inclui este estado no conjunto usado para decidir as ações ou a aparência do pedido.
        "Pagamento Recusado",

        // Inclui este estado no conjunto usado para decidir as ações ou a aparência do pedido.
        "Estoque Indisponível",

        // Inclui este estado no conjunto usado para decidir as ações ou a aparência do pedido.
        "Pedido Cancelado",

      // Confere se o estado do pedido pertence ao conjunto definido acima.
      ].includes(p.estado);

      // Disponibiliza checkout apenas quando há URL e o pedido ainda aceita pagamento.
      const podePagar = p.checkout_url && !encerrado;

      // Completa esta expressão com os argumentos ou valores utilizados na etapa desenharPedidos.
      return (

        // Define o cartão de produto ou pedido.
        `<article class="pedido-card">` +

        // Agrupa visualmente os elementos desta parte do cartão.
        `<div class="pedido-cabecalho">` +

        // Agrupa visualmente os elementos desta parte do cartão.
        `<div>` +

        // Exibe o nome do produto ou a identificação resumida do pedido.
        `<h3>Pedido #${escapar(p.pedido_id.slice(0, 8))} · ${dinheiro(p.total_centavos)}</h3>` +

        // Define o callback que transforma ou processa o elemento atual da coleção.
        `<p>${p.itens.map((i) => `${i.quantidade}× ${escapar(i.nome)}`).join(" · ")}</p>` +

        // Fecha o elemento HTML aberto no trecho anterior.
        `</div>` +

        // Mostra a etiqueta, o estado ou uma etapa da linha do tempo.
        `<span class="status ${erro ? "erro" : ""}">${escapar(p.estado)}</span>` +

        // Fecha o elemento HTML aberto no trecho anterior.
        `</div>` +

        // Define o callback que transforma ou processa o elemento atual da coleção.
        `<div class="timeline">${p.historico.map((h) => `<span class="etapa" title="${escapar(new Date(h.criado_em).toLocaleString("pt-BR"))}">✓ ${escapar(h.notificacao || h.estado)}</span>`).join("")}</div>${p.nota_id ? `<p class="nota">Nota fiscal simulada: ${escapar(p.nota_id)}</p>` : ""}<div class="pedido-acoes">${podePagar ? `<a class="botao pagar" href="${escapar(p.checkout_url)}" target="_blank" rel="noopener noreferrer">Abrir pagamento ↗</a>` : ""}${!encerrado ? `<button class="link-botao cancelar-pedido" data-pedido="${escapar(p.pedido_id)}">Cancelar pedido</button>` : ""}</div>` +

        // Fecha o elemento HTML aberto no trecho anterior.
        `</article>`

      // Fecha o bloco, callback, chamada ou coleção iniciado acima.
      );

    // Fecha o bloco, callback, chamada ou coleção iniciado acima.
    })

    // Une os trechos gerados em uma única string HTML ou descrição de itens.
    .join("");

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
}

// Agrupa atualizações concorrentes para que uma notificação SSE não seja perdida.
function carregarPedidos() {

  // Detecta uma consulta já em andamento para reutilizar sua Promise.
  if (atualizacaoPedidos) {

    // Sinaliza que outra atualização chegou durante a consulta em andamento.
    atualizarNovamente = true;

    // Devolve a mesma Promise aos interessados na atualização em andamento.
    return atualizacaoPedidos;

  // Fecha o bloco, callback, chamada ou coleção iniciado acima.
  }

  // Guarda a Promise da consulta em andamento para coordenar atualizações concorrentes.
  atualizacaoPedidos = (async () => {

    // Executa a operação protegida pelo tratamento de erros abaixo.
    try {

      // Inicia uma consulta que será repetida se outra atualização chegar durante a espera.
      do {

        // Sinaliza que outra atualização chegou durante a consulta em andamento.
        atualizarNovamente = false;

        // Mantém os pedidos carregados para o cliente deste navegador.
        pedidos = await api("/pedidos?cliente=" + cliente);

        // Atualiza o DOM com o estado e o histórico de pedidos disponíveis.
        desenharPedidos();

      // Repete a consulta para incluir as mudanças que chegaram durante a requisição anterior.
      } while (atualizarNovamente);

    // Trata a falha sem apresentá-la como sucesso ao usuário.
    } catch (e) {

      // Apresenta ao usuário o resultado ou a falha desta operação.
      aviso(e.message, true);

    // Restaura os controles mesmo quando a operação termina com erro.
    } finally {

      // Guarda a Promise da consulta em andamento para coordenar atualizações concorrentes.
      atualizacaoPedidos = null;

    // Fecha o bloco, callback, chamada ou coleção iniciado acima.
    }

  // Completa esta expressão com os argumentos ou valores utilizados na etapa carregarPedidos.
  })();

  // Devolve a mesma Promise aos interessados na atualização em andamento.
  return atualizacaoPedidos;

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
}

// Registra um callback para responder à interação ou à mensagem indicada.
$("#lista-pedidos").addEventListener("click", async (e) => {

  // Localiza o botão responsável pela interação atual.
  const b = e.target.closest(".cancelar-pedido");

  // Ignora cliques em áreas que não correspondem ao botão esperado.
  if (!b) return;

  // Bloqueia o botão durante a requisição para evitar cliques repetidos.
  b.disabled = true;

  // Executa a operação protegida pelo tratamento de erros abaixo.
  try {

    // Completa esta expressão com os argumentos ou valores utilizados na etapa atual.
    await api("/pedidos/" + b.dataset.pedido + "?cliente=" + cliente, {

      // Define o método HTTP adequado ao comando REST desta operação.
      method: "DELETE",

    // Fecha o bloco, callback, chamada ou coleção iniciado acima.
    });

    // Aguarda a consulta do estado atual dos pedidos após o comando ou evento SSE.
    await carregarPedidos();

    // Apresenta ao usuário o resultado ou a falha desta operação.
    aviso("Cancelamento solicitado. A reserva será devolvida.");

  // Trata a falha sem apresentá-la como sucesso ao usuário.
  } catch (e) {

    // Apresenta ao usuário o resultado ou a falha desta operação.
    aviso(e.message, true);

    // Libera o botão para uma nova tentativa depois da resposta ou falha.
    b.disabled = false;

  // Fecha o bloco, callback, chamada ou coleção iniciado acima.
  }

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
});

// Abre o EventSource do cliente; o navegador reconecta e envia Last-Event-ID automaticamente.
const eventos = new EventSource(API + "/eventos?cliente=" + cliente);

// Define o callback que transforma ou processa o elemento atual da coleção.
eventos.onopen = () => {

  // Atualiza o texto visível sem interpretar conteúdo recebido como HTML.
  $("#conexao").textContent = "Tempo real conectado";

  // Marca o indicador de conexão como ativo.
  $("#conexao").classList.add("online");

  // Solicita a atualização dos pedidos deste navegador por REST.
  carregarPedidos();

  // Solicita uma nova leitura do catálogo e dos saldos por REST.
  carregarProdutos();

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
};

// Define o callback que transforma ou processa o elemento atual da coleção.
eventos.onerror = () => {

  // Atualiza o texto visível sem interpretar conteúdo recebido como HTML.
  $("#conexao").textContent = "Reconectando…";

  // Remove a aparência de conexão ativa até o stream reconectar.
  $("#conexao").classList.remove("online");

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
};

// Encadeia as atualizações SSE para processar uma notificação de cada vez.
let filaAtualizacao = Promise.resolve();

// Registra um callback para responder à interação ou à mensagem indicada.
eventos.addEventListener("pedido", (e) => {

  // Encadeia as atualizações SSE para processar uma notificação de cada vez.
  filaAtualizacao = filaAtualizacao

    // Define o callback que transforma ou processa o elemento atual da coleção.
    .then(async () => {

      // Interpreta os dados JSON da resposta HTTP ou da notificação SSE.
      const d = JSON.parse(e.data);

      // Aguarda a consulta do estado atual dos pedidos após o comando ou evento SSE.
      await carregarPedidos();

      // Apresenta ao usuário o resultado ou a falha desta operação.
      if (d.tipo !== "pedido.criado") aviso(d.notificacao || d.estado);

      // Verifica esta condição antes de aplicar a atualização ou continuar o fluxo.
      if (

        // Inicia a coleção de valores que será usada nesta verificação.
        [

          // Fornece o valor textual ou a configuração deste campo.
          "pedido.estoque_ok",

          // Fornece o valor textual ou a configuração deste campo.
          "pedido.excluido",

          // Fornece o valor textual ou a configuração deste campo.
          "pagamento.recusado",

          // Fornece o valor textual ou a configuração deste campo.
          "estoque.indisponivel",

        // Completa esta expressão com os argumentos ou valores utilizados na etapa atual.
        ].includes(d.tipo)

      // Fecha o bloco, callback, chamada ou coleção iniciado acima.
      )

        // Atualiza o saldo exibido depois de uma operação que pode alterar reservas.
        await carregarProdutos();

    // Fecha o bloco, callback, chamada ou coleção iniciado acima.
    })

    // Define o callback que transforma ou processa o elemento atual da coleção.
    .catch(() =>

      // Apresenta ao usuário o resultado ou a falha desta operação.
      aviso("Falha ao atualizar pedidos. Reconecte a página.", true),

    // Fecha o bloco, callback, chamada ou coleção iniciado acima.
    );

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
});

// Restaura e-mail e categorias cadastradas para o cliente deste navegador.
async function carregarInteresse() {

  // Executa a operação protegida pelo tratamento de erros abaixo.
  try {

    // Interpreta os dados JSON da resposta HTTP ou da notificação SSE.
    const d = await api("/interesses?cliente=" + cliente);

    // Completa esta expressão com os argumentos ou valores utilizados na etapa carregarInteresse.
    $("#email").value = d.email;

    // Seleciona no documento os controles que receberão os eventos.
    document

      // Seleciona todos os elementos que correspondem ao seletor CSS indicado.
      .querySelectorAll("[name=categoria]")

      // Reflete nas caixas de seleção as categorias devolvidas pelo Gateway.
      .forEach((c) => (c.checked = d.categorias.includes(c.value)));

  // Trata a falha sem apresentá-la como sucesso ao usuário.
  } catch (e) {

    // Apresenta ao usuário o resultado ou a falha desta operação.
    aviso(e.message, true);

  // Fecha o bloco, callback, chamada ou coleção iniciado acima.
  }

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
}

// Registra um callback para responder à interação ou à mensagem indicada.
$("#interesse-form").addEventListener("submit", async (e) => {

  // Impede o envio tradicional do formulário e mantém a página aberta para usar REST.
  e.preventDefault();

  // Localiza o botão responsável pela interação atual.
  const b = e.submitter;

  // Bloqueia o botão durante a requisição para evitar cliques repetidos.
  b.disabled = true;

  // Executa a operação protegida pelo tratamento de erros abaixo.
  try {

    // Relaciona as categorias A, B e C aos nomes exibidos na loja.
    const categorias = [

      // Completa esta expressão com os argumentos ou valores utilizados na etapa atual.
      ...document.querySelectorAll("[name=categoria]:checked"),

    // Define o callback que transforma ou processa o elemento atual da coleção.
    ].map((c) => c.value);

    // Exige ao menos uma categoria no cadastro; o cancelamento possui um botão próprio.
    if (!categorias.length)

      // Transforma a condição de falha em mensagem para o tratamento de erro da interface.
      throw new Error(

        // Fornece o valor textual ou a configuração deste campo.
        "Selecione ao menos uma categoria ou cancele a inscrição.",

      // Fecha o bloco, callback, chamada ou coleção iniciado acima.
      );

    // Completa esta expressão com os argumentos ou valores utilizados na etapa atual.
    await api("/interesses", {

      // Define o método HTTP adequado ao comando REST desta operação.
      method: "PUT",

      // Serializa o corpo JSON com os dados necessários ao comando REST.
      body: JSON.stringify({ cliente, email: $("#email").value, categorias }),

    // Fecha o bloco, callback, chamada ou coleção iniciado acima.
    });

    // Atualiza o texto visível sem interpretar conteúdo recebido como HTML.
    $("#interesse-mensagem").textContent =

      // Fornece o valor textual ou a configuração deste campo.
      "Interesses salvos. Você receberá ofertas das categorias selecionadas.";

  // Trata a falha sem apresentá-la como sucesso ao usuário.
  } catch (e) {

    // Atualiza o texto visível sem interpretar conteúdo recebido como HTML.
    $("#interesse-mensagem").textContent = e.message;

  // Restaura os controles mesmo quando a operação termina com erro.
  } finally {

    // Libera o botão para uma nova tentativa depois da resposta ou falha.
    b.disabled = false;

  // Fecha o bloco, callback, chamada ou coleção iniciado acima.
  }

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
});

// Registra um callback para responder à interação ou à mensagem indicada.
$("#cancelar-interesse").addEventListener("click", async () => {

  // Executa a operação protegida pelo tratamento de erros abaixo.
  try {

    // Completa esta expressão com os argumentos ou valores utilizados na etapa atual.
    await api("/interesses?cliente=" + cliente, { method: "DELETE" });

    // Seleciona no documento os controles que receberão os eventos.
    document

      // Seleciona todos os elementos que correspondem ao seletor CSS indicado.
      .querySelectorAll("[name=categoria]")

      // Reflete nas caixas de seleção as categorias devolvidas pelo Gateway.
      .forEach((c) => (c.checked = false));

    // Atualiza o texto visível sem interpretar conteúdo recebido como HTML.
    $("#interesse-mensagem").textContent =

      // Fornece o valor textual ou a configuração deste campo.
      "Cancelamento solicitado. Você não receberá novas promoções após o processamento.";

  // Trata a falha sem apresentá-la como sucesso ao usuário.
  } catch (e) {

    // Atualiza o texto visível sem interpretar conteúdo recebido como HTML.
    $("#interesse-mensagem").textContent = e.message;

  // Fecha o bloco, callback, chamada ou coleção iniciado acima.
  }

// Fecha o bloco, callback, chamada ou coleção iniciado acima.
});

// Solicita a atualização dos pedidos deste navegador por REST.
Promise.all([carregarProdutos(), carregarPedidos(), carregarInteresse()]);
