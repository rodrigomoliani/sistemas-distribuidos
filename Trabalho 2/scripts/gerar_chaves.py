# Preparação local de RSA: python -m scripts.gerar_chaves, com os serviços parados.
# Não usa RabbitMQ. Arquivos gerados em chaves/ são ignorados pelo Git.
# A privada fica com seu produtor; cópias públicas permitem verificar as assinaturas.

# Biblioteca que gera pares RSA e importa/exporta chaves PEM.
from Crypto.PublicKey import RSA

# Obtém a pasta do trabalho e os nomes dos cinco produtores.
from comum.seguranca import RAIZ, SERVICOS


# Cria as chaves necessárias e distribui apenas as partes públicas.
def main():

    # Mapa temporário de produtor para bytes de sua chave pública.
    publicas = {}

    # Percorre Principal, Estoque, Pagamento, Entrega e Promoções.
    for servico in SERVICOS:

        # Monta o caminho local da pasta de chaves do produtor atual.
        pasta = RAIZ / servico / "chaves"

        # Cria diretórios intermediários; exist_ok evita erro se já existirem.
        pasta.mkdir(parents=True, exist_ok=True)

        # Caminho do arquivo privado desse serviço.
        privada = pasta / "privada.pem"

        # Preserva a privada existente; só gera se ainda não houver arquivo.
        if not privada.exists():

            # Gera RSA de 2048 bits, exporta em PEM e grava os bytes no arquivo local.
            # A privada não é cifrada por senha aqui; deve permanecer fora do repositório.
            privada.write_bytes(RSA.generate(2048).export_key())

        # Importa a chave gravada ou a chave que já existia no diretório.
        chave = RSA.import_key(privada.read_bytes())

        # Confere que contém a parte privada e tem tamanho de pelo menos 2048 bits.
        if not chave.has_private() or chave.size_in_bits() < 2048:

            # Interrompe a preparação se encontrar uma chave inadequada.
            raise ValueError(f"Chave privada inválida em {servico}.")

        # Extrai só a parte pública e guarda seus bytes exportados por produtor.
        publicas[servico] = chave.public_key().export_key()

    # Expande a tupla SERVICOS e acrescenta a pasta compartilhada de C1/C2.
    for destinatario in (*SERVICOS, "consumidores"):

        # Caminho onde cada destinatário guarda cópias públicas confiáveis.
        pasta = RAIZ / destinatario / "chaves" / "publicas"

        # Cria o diretório de distribuição caso ele ainda não exista.
        pasta.mkdir(parents=True, exist_ok=True)

        # Percorre todas as chaves públicas disponíveis para distribuição.
        for produtor, chave in publicas.items():

            # Os cinco serviços recebem todas; consumidores recebem somente Promoções.
            if destinatario != "consumidores" or produtor == "promocoes":

                # Grava a chave pública com o nome do produtor, usado depois por Assinador.
                (pasta / f"{produtor}.pem").write_bytes(chave)

    # Informa o fim da preparação sem imprimir o conteúdo das chaves.
    print("Chaves prontas. Chaves privadas existentes foram preservadas.", flush=True)


# Ponto de entrada ao executar o script com python -m.
if __name__ == "__main__":

    # Chama a geração/distribuição local.
    main()
