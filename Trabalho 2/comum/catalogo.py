# Catálogo fixo e validação local do formato dos pedidos.
# Este módulo não envia mensagens nem consulta saldo no RabbitMQ. Cada processo
# importa suas próprias definições; o estoque atualizado fica no serviço Estoque.

# Mapa de ID textual para nome, categoria e preço em centavos.
# Inteiros em centavos evitam arredondamentos de ponto flutuante nos pedidos.
CATALOGO = {

    # Produto 1: Caderno, categoria A, preço de R$ 15,00.
    "1": {"nome": "Caderno", "categoria": "A", "preco_centavos": 1500},

    # Produto 2: Camiseta, categoria B, preço de R$ 50,00.
    "2": {"nome": "Camiseta", "categoria": "B", "preco_centavos": 5000},

    # Produto 3: Fone, categoria C, preço de R$ 80,00.
    "3": {"nome": "Fone", "categoria": "C", "preco_centavos": 8000},
}

# Saldo inicial por produto; não representa o saldo atualizado ao longo da sessão.
ESTOQUE_INICIAL = 10


# Converte centavos em texto somente para exibição.
def dinheiro(centavos):

    # // 100 dá a parte em reais; % 100 dá os centavos restantes.
    # :02d preenche com zero à esquerda: 1505 fica R$ 15,05.
    return f"R$ {centavos // 100},{centavos % 100:02d}"


# Recebe pares (produto_id, quantidade) e constrói os itens completos.
def montar_itens(selecao):
    """Agrupa produtos repetidos e aplica os preços do catálogo local."""

    # Acumulador que soma quantidades por produto.
    quantidades = {}

    # Desempacota cada par em ID e quantidade.
    for produto_id, quantidade in selecao:

        # Exige ID string e existente no catálogo. O or usa curto-circuito:
        # se não for string, não tenta pesquisar esse valor no dicionário.
        if not isinstance(produto_id, str) or produto_id not in CATALOGO:

            # Rejeita produto desconhecido antes de produzir a lista de itens.
            raise ValueError(f"Produto desconhecido: {produto_id}")

        # Exige int exato, excluindo bool (em Python bool é uma subclasse de int).
        # Também recusa quantidade zero ou negativa.
        if type(quantidade) is not int or quantidade <= 0:

            # Propaga a falha para o menu ou consumidor que chamou a validação.
            raise ValueError("A quantidade deve ser um inteiro positivo.")

        # get consulta o acumulador local, usando zero para um ID ainda não visto.
        # Soma repetições: duas entradas com 2 e 3 unidades viram uma com 5.
        quantidades[produto_id] = quantidades.get(produto_id, 0) + quantidade

    # Um dicionário vazio indica que nenhum produto foi informado.
    if not quantidades:

        # Recusa criar um pedido sem itens.
        raise ValueError("O pedido precisa conter pelo menos um produto.")

    # Compreensão de lista: monta um dicionário para cada produto agrupado.
    return [

        # Inclui o ID e a quantidade consolidada daquele produto.
        {"produto_id": produto_id, "quantidade": quantidade,

         # Busca o nome no catálogo, sem confiar em texto fornecido pela entrada.
         "nome": CATALOGO[produto_id]["nome"],

         # Busca o preço unitário oficial local; promoções não alteram este catálogo.
         "preco_unitario_centavos": CATALOGO[produto_id]["preco_centavos"]}

        # Percorre os produtos na ordem em que apareceram pela primeira vez.
        for produto_id, quantidade in quantidades.items()
    ]


# Confere dados de um pedido; retorna None implicitamente se estiver correto.
# Falhas geram ValueError. Assinatura válida não substitui essas regras de negócio.
def validar_pedido(dados):

    # Exige pedido_id textual e não vazio. get devolve None se faltar;
    # o curto-circuito evita acessar a chave ausente na segunda condição.
    if not isinstance(dados.get("pedido_id"), str) or not dados["pedido_id"]:

        # Recusa pedido sem identificação utilizável.
        raise ValueError("pedido_id ausente.")

    # Exige cliente textual com conteúdo após remover espaços das pontas.
    if not isinstance(dados.get("cliente"), str) or not dados["cliente"].strip():

        # Recusa nome ausente, vazio ou composto somente por espaços.
        raise ValueError("Cliente ausente.")

    # Lê a lista de itens do dicionário recebido.
    itens = dados.get("itens")

    # Exige uma lista não vazia.
    if not isinstance(itens, list) or not itens:

        # Recusa estrutura sem produtos.
        raise ValueError("Itens ausentes.")

    # Lista auxiliar para reconstruir os itens a partir de ID e quantidade.
    selecao = []

    # Examina cada item recebido no pedido.
    for item in itens:

        # Cada item deve ser um dicionário, como os objetos JSON do contrato.
        if not isinstance(item, dict):

            # Recusa valores de outro tipo antes de tentar acessar os campos.
            raise ValueError("Item inválido.")

        # Extrai pares para montar_itens; campos ausentes viram None e serão recusados.
        selecao.append((item.get("produto_id"), item.get("quantidade")))

    # Reaplica a validação e recupera nomes/preços do catálogo local.
    esperados = montar_itens(selecao)

    # Compara listas e dicionários: identifica itens ou valores que divergem
    # da reconstrução, incluindo repetições que deveriam ter sido agrupadas.
    if itens != esperados:

        # Impede aceitar um pedido diferente do catálogo e do formato esperado.
        raise ValueError("Itens ou preços divergem do catálogo.")

    # Soma quantidade vezes preço unitário; o contrato usa inteiros em centavos.
    total = sum(i["quantidade"] * i["preco_unitario_centavos"] for i in itens)

    # Exige total inteiro (sem bool) e igual à soma recalculada.
    if type(dados.get("total_centavos")) is not int or dados["total_centavos"] != total:

        # Rejeita um total incompatível com os itens.
        raise ValueError("Total do pedido inválido.")
