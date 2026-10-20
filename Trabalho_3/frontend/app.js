"use strict";

const API = window.API_URL;
const $ = (s) => document.querySelector(s);

// Restaura ou gera UUID do cliente para a sessão do navegador
let cliente = localStorage.getItem("campus.cliente");
if (!cliente) {
  cliente = crypto.randomUUID();
  localStorage.setItem("campus.cliente", cliente);
}

let produtos = [];
let carrinho = {};
let categoria = "";
let pedidos = [];
let atualizacaoPedidos = null;
let atualizarNovamente = false;
let pendente = false;

const dinheiro = (n) =>
  new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL" }).format(n / 100);

const categorias = { A: "Papelaria", B: "Vestuário", C: "Eletrônicos" };

const nomes = {
  1: "Para todas as suas ideias.",
  2: "Conforto para qualquer dia.",
  3: "Sua trilha sonora, por perto.",
};

const escapar = (s) =>
  String(s ?? "").replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]
  );

// Ilustrações SVG locais para os produtos
const artes = {
  A: (
    '<svg viewBox="0 0 130 150" aria-hidden="true">' +
    '<g transform="rotate(-10 65 75)">' +
    '<rect x="29" y="22" width="79" height="111" rx="3" fill="#cbd8b6"/>' +
    '<rect x="23" y="18" width="79" height="111" rx="3" fill="#aabd95"/>' +
    '<path d="M32 18v111" stroke="#7e986a"/>' +
    '<text x="44" y="60" font-family="sans-serif" font-weight="bold" font-size="12" fill="#365639">GOOD</text>' +
    '<text x="44" y="75" font-family="sans-serif" font-weight="bold" font-size="12" fill="#365639">IDEAS</text>' +
    '<text x="44" y="90" font-family="sans-serif" font-weight="bold" font-size="12" fill="#365639">START</text>' +
    '<text x="44" y="105" font-family="sans-serif" font-weight="bold" font-size="12" fill="#365639">HERE.</text>' +
    "</g></svg>"
  ),
  B: (
    '<svg viewBox="0 0 150 150" aria-hidden="true">' +
    '<path d="M51 28L28 39 10 67l24 13 13-17v62h58V63l13 17 24-13-18-28-23-11c-7 10-13 13-25 13S58 38 51 28" fill="#c6b899"/>' +
    '<path d="M51 28c3 15 14 20 25 20s22-5 25-20" fill="none" stroke="#ab9a78" stroke-width="3"/>' +
    '<text x="61" y="83" font-size="10" font-family="sans-serif" fill="#6f654e">campus</text>' +
    "</svg>"
  ),
  C: (
    '<svg viewBox="0 0 150 150" aria-hidden="true">' +
    '<path d="M33 87V67c0-55 85-55 85 0v20" fill="none" stroke="#344851" stroke-width="14"/>' +
    '<path d="M34 76V64c0-47 82-47 82 0v12" fill="none" stroke="#667a83" stroke-width="4"/>' +
    '<rect x="22" y="70" width="25" height="48" rx="10" fill="#344851"/>' +
    '<rect x="105" y="70" width="25" height="48" rx="10" fill="#344851"/>' +
    '<rect x="38" y="76" width="15" height="40" rx="7" fill="#63777f"/>' +
    '<rect x="99" y="76" width="15" height="40" rx="7" fill="#63777f"/>' +
    "</svg>"
  ),
};

// Cliente HTTP REST para chamadas ao Gateway
async function api(caminho, opcoes = {}) {
  const r = await fetch(API + caminho, {
    ...opcoes,
    headers: { "Content-Type": "application/json", ...opcoes.headers },
  });

  const d = await r.json();
  if (!r.ok) {
    throw new Error(typeof d.detail === "string" ? d.detail : "Confira os dados e tente novamente.");
  }
  return d;
}

let toastTimer;
function aviso(texto, erro = false) {
  const el = $("#mensagem");
  el.textContent = texto;
  el.classList.toggle("erro", erro);
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => (el.hidden = true), 6500);
}

function desenharProdutos() {
  const filtrados = produtos.filter((p) => !categoria || p.categoria === categoria);

  $("#produtos").innerHTML =
    filtrados
      .map(
        (p) =>
          `<article class="produto">` +
          `<div class="produto-arte ${p.categoria}">` +
          `<span class="categoria-tag">${categorias[p.categoria]}</span>${artes[p.categoria]}</div>` +
          `<div class="produto-info">` +
          `<h3>${escapar(p.nome)}</h3>` +
          `<p class="produto-sub">${nomes[p.id] || ""} · ${p.quantidade} disponíveis</p>` +
          `<div class="produto-preco">` +
          `<strong>${dinheiro(p.preco_centavos)}</strong>` +
          `<button class="adicionar" data-produto="${escapar(p.id)}" aria-label="Adicionar ${escapar(p.nome)}" ${p.quantidade <= 0 ? "disabled" : ""}>+</button>` +
          `</div></div></article>`
      )
      .join("") || '<p class="vazio sem-produtos">Nenhum produto disponível nesta categoria.</p>';
}

function desenharCarrinho() {
  let total = 0;
  let quantidade = 0;

  const itens = Object.entries(carrinho)
    .map(([pid, q]) => {
      const p = produtos.find((p) => p.id === pid);
      if (!p) return "";
      total += q * p.preco_centavos;
      quantidade += q;
      return (
        `<div class="sacola-item">` +
        `<div><strong>${escapar(p.nome)}</strong><span>${dinheiro(p.preco_centavos)}</span></div>` +
        `<div class="contador">` +
        `<button data-ajuste="-1" data-produto="${pid}" aria-label="Remover uma unidade de ${escapar(p.nome)}">−</button>` +
        `<span>${q}</span>` +
        `<button data-ajuste="1" data-produto="${pid}" aria-label="Adicionar uma unidade de ${escapar(p.nome)}">+</button>` +
        `</div></div>`
      );
    })
    .join("");

  $("#itens-sacola").innerHTML = itens || '<p class="vazio">Escolha um produto para começar.</p>';
  $("#total").textContent = dinheiro(total);
  $("#quantidade-sacola").textContent = quantidade;
  $("#finalizar").disabled = quantidade === 0 || pendente;
}

async function carregarProdutos() {
  try {
    produtos = await api("/produtos");
    desenharProdutos();
    desenharCarrinho();
  } catch (e) {
    $("#produtos").innerHTML =
      '<p class="vazio sem-produtos">Não foi possível consultar o estoque. Use “Atualizar estoque” para tentar novamente.</p>';
    aviso(e.message, true);
  }
}

$("#atualizar").addEventListener("click", carregarProdutos);

document.querySelectorAll(".filtro").forEach((b) =>
  b.addEventListener("click", () => {
    categoria = b.dataset.categoria;
    document.querySelectorAll(".filtro").forEach((x) => x.classList.toggle("ativo", x === b));
    desenharProdutos();
  })
);

$("#produtos").addEventListener("click", (e) => {
  const b = e.target.closest("[data-produto]");
  if (!b) return;
  alterar(b.dataset.produto, 1);
});

$("#itens-sacola").addEventListener("click", (e) => {
  const b = e.target.closest("[data-ajuste]");
  if (b) alterar(b.dataset.produto, Number(b.dataset.ajuste));
});

function alterar(pid, ajuste) {
  const p = produtos.find((p) => p.id === pid);
  const nova = (carrinho[pid] || 0) + ajuste;

  if (nova > p.quantidade) {
    aviso("Quantidade acima do estoque disponível.", true);
    return;
  }

  if (nova <= 0) {
    delete carrinho[pid];
  } else {
    carrinho[pid] = nova;
  }

  desenharCarrinho();
}

$("#nome").value = localStorage.getItem("campus.nome") || "";

$("#pedido-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (pendente) return;
  pendente = true;
  desenharCarrinho();

  try {
    const nome = $("#nome").value.trim();
    if (!nome) throw new Error("Informe seu nome.");

    localStorage.setItem("campus.nome", nome);

    const p = await api("/pedidos", {
      method: "POST",
      body: JSON.stringify({
        cliente,
        nome,
        itens: Object.entries(carrinho).map(([produto_id, quantidade]) => ({
          produto_id,
          quantidade,
        })),
      }),
    });

    carrinho = {};
    pedidos.unshift(p);
    desenharPedidos();
    aviso("Pedido criado. Aguarde a confirmação do estoque para pagar.");
    $("#pedidos").scrollIntoView({ behavior: "smooth" });
    await carregarProdutos();
  } catch (e) {
    aviso(e.message, true);
  } finally {
    pendente = false;
    desenharCarrinho();
  }
});

function desenharPedidos() {
  const el = $("#lista-pedidos");
  if (!pedidos.length) {
    el.innerHTML =
      '<p class="vazio grande">Seus pedidos aparecerão aqui. Encontre seu próximo favorito no catálogo.</p>';
    return;
  }

  el.innerHTML = pedidos
    .map((p) => {
      const encerrado = [
        "Pedido Enviado",
        "Pagamento Aprovado",
        "Pagamento Recusado",
        "Estoque Indisponível",
        "Pedido Cancelado",
      ].includes(p.estado);

      const erro = [
        "Pagamento Recusado",
        "Estoque Indisponível",
        "Pedido Cancelado",
      ].includes(p.estado);

      const podePagar = p.checkout_url && !encerrado;

      return (
        `<article class="pedido-card">` +
        `<div class="pedido-cabecalho">` +
        `<div>` +
        `<h3>Pedido #${escapar(p.pedido_id.slice(0, 8))} · ${dinheiro(p.total_centavos)}</h3>` +
        `<p>${p.itens.map((i) => `${i.quantidade}× ${escapar(i.nome)}`).join(" · ")}</p>` +
        `</div>` +
        `<span class="status ${erro ? "erro" : ""}">${escapar(p.estado)}</span>` +
        `</div>` +
        `<div class="timeline">${p.historico.map((h) => `<span class="etapa" title="${escapar(new Date(h.criado_em).toLocaleString("pt-BR"))}">✓ ${escapar(h.notificacao || h.estado)}</span>`).join("")}</div>` +
        `${p.nota_id ? `<p class="nota">Nota fiscal simulada: ${escapar(p.nota_id)}</p>` : ""}` +
        `<div class="pedido-acoes">` +
        `${podePagar ? `<a class="botao pagar" href="${escapar(p.checkout_url)}" target="_blank" rel="noopener noreferrer">Abrir pagamento ↗</a>` : ""}` +
        `${!encerrado ? `<button class="link-botao cancelar-pedido" data-pedido="${escapar(p.pedido_id)}">Cancelar pedido</button>` : ""}` +
        `</div></article>`
      );
    })
    .join("");
}

function carregarPedidos() {
  if (atualizacaoPedidos) {
    atualizarNovamente = true;
    return atualizacaoPedidos;
  }

  atualizacaoPedidos = (async () => {
    try {
      do {
        atualizarNovamente = false;
        pedidos = await api("/pedidos?cliente=" + cliente);
      } while (atualizarNovamente);
      desenharPedidos();
    } catch (e) {
      aviso(e.message, true);
    } finally {
      atualizacaoPedidos = null;
    }
  })();

  return atualizacaoPedidos;
}

$("#lista-pedidos").addEventListener("click", async (e) => {
  const b = e.target.closest(".cancelar-pedido");
  if (!b) return;

  b.disabled = true;
  try {
    await api("/pedidos/" + b.dataset.pedido + "?cliente=" + cliente, {
      method: "DELETE",
    });
    await carregarPedidos();
    aviso("Cancelamento solicitado. A reserva será devolvida.");
  } catch (e) {
    aviso(e.message, true);
    b.disabled = false;
  }
});

// Conexão em tempo real Server-Sent Events (SSE)
const eventos = new EventSource(API + "/eventos?cliente=" + cliente);

eventos.onopen = () => {
  $("#conexao").textContent = "Tempo real conectado";
  $("#conexao").classList.add("online");
  carregarPedidos();
  carregarProdutos();
};

eventos.onerror = () => {
  $("#conexao").textContent = "Reconectando…";
  $("#conexao").classList.remove("online");
};

let filaAtualizacao = Promise.resolve();
eventos.addEventListener("pedido", (e) => {
  filaAtualizacao = filaAtualizacao
    .then(async () => {
      const d = JSON.parse(e.data);
      await carregarPedidos();
      if (d.tipo !== "pedido.criado") aviso(d.notificacao || d.estado);

      if (
        [
          "pedido.estoque_ok",
          "pedido.excluido",
          "pagamento.recusado",
          "estoque.indisponivel",
        ].includes(d.tipo)
      ) {
        await carregarProdutos();
      }
    })
    .catch(() => aviso("Falha ao atualizar pedidos. Reconecte a página.", true));
});

async function carregarInteresse() {
  try {
    const d = await api("/interesses?cliente=" + cliente);
    $("#email").value = d.email;
    document
      .querySelectorAll("[name=categoria]")
      .forEach((c) => (c.checked = d.categorias.includes(c.value)));
  } catch (e) {
    aviso(e.message, true);
  }
}

$("#interesse-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const b = e.submitter;
  b.disabled = true;

  try {
    const categoriasSelecionadas = [
      ...document.querySelectorAll("[name=categoria]:checked"),
    ].map((c) => c.value);

    if (!categoriasSelecionadas.length) {
      throw new Error("Selecione ao menos uma categoria ou cancele a inscrição.");
    }

    await api("/interesses", {
      method: "PUT",
      body: JSON.stringify({ cliente, email: $("#email").value, categorias: categoriasSelecionadas }),
    });

    $("#interesse-mensagem").textContent =
      "Interesses salvos. Você receberá ofertas das categorias selecionadas.";
  } catch (e) {
    $("#interesse-mensagem").textContent = e.message;
  } finally {
    b.disabled = false;
  }
});

$("#cancelar-interesse").addEventListener("click", async () => {
  try {
    await api("/interesses?cliente=" + cliente, { method: "DELETE" });
    document.querySelectorAll("[name=categoria]").forEach((c) => (c.checked = false));
    $("#interesse-mensagem").textContent =
      "Cancelamento solicitado. Você não receberá novas promoções após o processamento.";
  } catch (e) {
    $("#interesse-mensagem").textContent = e.message;
  }
});

// Inicialização da interface
Promise.all([carregarProdutos(), carregarPedidos(), carregarInteresse()]);
