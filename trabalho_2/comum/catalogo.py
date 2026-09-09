CATALOGO = {
    "1": {"nome": "Caderno", "categoria": "A", "preco_centavos": 1500},
    "2": {"nome": "Camiseta", "categoria": "B", "preco_centavos": 5000},
    "3": {"nome": "Fone", "categoria": "C", "preco_centavos": 8000},
}
ESTOQUE_INICIAL = 10


def dinheiro(centavos):
    return f"R$ {centavos // 100},{centavos % 100:02d}"


def montar_itens(selecao):
    """Agrupa produtos repetidos e aplica os preços do catálogo local."""
    quantidades = {}
    for produto_id, quantidade in selecao:
        if produto_id not in CATALOGO:
            raise ValueError(f"Produto desconhecido: {produto_id}")
        if type(quantidade) is not int or quantidade <= 0:
            raise ValueError("A quantidade deve ser um inteiro positivo.")
        quantidades[produto_id] = quantidades.get(produto_id, 0) + quantidade
    if not quantidades:
        raise ValueError("O pedido precisa conter pelo menos um produto.")
    return [
        {"produto_id": produto_id, "quantidade": quantidade,
         "nome": CATALOGO[produto_id]["nome"],
         "preco_unitario_centavos": CATALOGO[produto_id]["preco_centavos"]}
        for produto_id, quantidade in quantidades.items()
    ]


def validar_pedido(dados):
    if not isinstance(dados.get("pedido_id"), str) or not dados["pedido_id"]:
        raise ValueError("pedido_id ausente.")
    if not isinstance(dados.get("cliente"), str) or not dados["cliente"].strip():
        raise ValueError("Cliente ausente.")
    itens = dados.get("itens")
    if not isinstance(itens, list) or not itens:
        raise ValueError("Itens ausentes.")
    selecao = []
    for item in itens:
        if not isinstance(item, dict):
            raise ValueError("Item inválido.")
        selecao.append((item.get("produto_id"), item.get("quantidade")))
    esperados = montar_itens(selecao)
    if itens != esperados:
        raise ValueError("Itens ou preços divergem do catálogo.")
    total = sum(i["quantidade"] * i["preco_unitario_centavos"] for i in itens)
    if type(dados.get("total_centavos")) is not int or dados["total_centavos"] != total:
        raise ValueError("Total do pedido inválido.")
