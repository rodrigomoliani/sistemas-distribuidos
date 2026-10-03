# Catálogo inicial e validação de pedidos. Valores monetários são inteiros em centavos.

# Prepara catálogo inicial dos produtos para esta etapa.
CATALOGO = {

    # Define o campo 1 desta estrutura de dados.
    "1": {"nome": "Caderno", "categoria": "A", "preco_centavos": 1500},

    # Define o campo 2 desta estrutura de dados.
    "2": {"nome": "Camiseta", "categoria": "B", "preco_centavos": 5000},

    # Define o campo 3 desta estrutura de dados.
    "3": {"nome": "Fone", "categoria": "C", "preco_centavos": 8000},

# Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
}

# Prepara saldo inicial de cada produto para esta etapa.
ESTOQUE_INICIAL = 10

# Formata um valor inteiro em centavos como reais, sem aritmética de ponto flutuante.
def dinheiro(centavos):

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return f"R$ {centavos // 100},{centavos % 100:02d}"

# Agrupa IDs repetidos e preenche nomes e preços do catálogo inicial.
def montar_itens(selecao):

    # Continua a expressão que prepara os dados desta operação.
    """Agrupa produtos repetidos e aplica os preços do catálogo local."""

    # Prepara quantidades agrupadas por produto para esta etapa.
    quantidades = {}

    # Percorre selecao para processar cada (produto_id, quantidade).
    for produto_id, quantidade in selecao:

        # Confere a condição not isinstance(produto_id, str) or produto_id not in CATALOGO antes de executar este bloco.
        if not isinstance(produto_id, str) or produto_id not in CATALOGO:

            # Interrompe a operação com erro: Produto desconhecido: .
            raise ValueError(f"Produto desconhecido: {produto_id}")

        # Confere a condição type(quantidade) is not int or quantidade <= 0 antes de executar este bloco.
        if type(quantidade) is not int or quantidade <= 0:

            # Interrompe a operação com erro: A quantidade deve ser um inteiro positivo.
            raise ValueError("A quantidade deve ser um inteiro positivo.")

        # Soma quantidades de linhas que se referem ao mesmo produto.
        quantidades[produto_id] = quantidades.get(produto_id, 0) + quantidade

    # Confere a condição not quantidades antes de executar este bloco.
    if not quantidades:

        # Interrompe a operação com erro: O pedido precisa conter pelo menos um produto.
        raise ValueError("O pedido precisa conter pelo menos um produto.")

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return [

        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
        {

            # Define o campo produto_id desta estrutura de dados.
            "produto_id": produto_id,

            # Define o campo quantidade desta estrutura de dados.
            "quantidade": quantidade,

            # Define o campo nome desta estrutura de dados.
            "nome": CATALOGO[produto_id]["nome"],

            # Define o campo preco_unitario_centavos desta estrutura de dados.
            "preco_unitario_centavos": CATALOGO[produto_id]["preco_centavos"],

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        }

        # Aplica esta iteração ou condição à expressão que está sendo construída.
        for produto_id, quantidade in quantidades.items()

    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
    ]

# Confere identificação, itens, quantidades, preços e total antes de aplicar uma regra.
def validar_pedido(dados):

    # Confere a condição not isinstance(dados.get('pedido_id'), str) or not dados['pedido_id'] antes de executar este bloco.
    if not isinstance(dados.get("pedido_id"), str) or not dados["pedido_id"]:

        # Interrompe a operação com erro: pedido_id ausente.
        raise ValueError("pedido_id ausente.")

    # Confere a condição not isinstance(dados.get('cliente'), str) or not dados['cliente'].strip() antes de executar este bloco.
    if not isinstance(dados.get("cliente"), str) or not dados["cliente"].strip():

        # Interrompe a operação com erro: Cliente ausente.
        raise ValueError("Cliente ausente.")

    # Prepara itens do pedido para esta etapa.
    itens = dados.get("itens")

    # Confere a condição not isinstance(itens, list) or not itens antes de executar este bloco.
    if not isinstance(itens, list) or not itens:

        # Interrompe a operação com erro: Itens ausentes.
        raise ValueError("Itens ausentes.")

    # Prepara seleção de produto e quantidade para esta etapa.
    selecao = []

    # Percorre itens para processar cada item.
    for item in itens:

        # Confere a condição not isinstance(item, dict) antes de executar este bloco.
        if not isinstance(item, dict):

            # Interrompe a operação com erro: Item inválido.
            raise ValueError("Item inválido.")

        # Acrescenta o resultado ao conjunto que está sendo construído nesta etapa.
        selecao.append((item.get("produto_id"), item.get("quantidade")))

    # Prepara itens reconstruídos com os preços corretos para esta etapa.
    esperados = montar_itens(selecao)

    # Confere a condição itens != esperados antes de executar este bloco.
    if itens != esperados:

        # Interrompe a operação com erro: Itens ou preços divergem do catálogo.
        raise ValueError("Itens ou preços divergem do catálogo.")

    # Prepara total em centavos para esta etapa.
    total = sum(i["quantidade"] * i["preco_unitario_centavos"] for i in itens)

    # Confere a condição type(dados.get('total_centavos')) is not int or dados['total_centavos'] != total antes de executar este bloco.
    if type(dados.get("total_centavos")) is not int or dados["total_centavos"] != total:

        # Interrompe a operação com erro: Total do pedido inválido.
        raise ValueError("Total do pedido inválido.")
