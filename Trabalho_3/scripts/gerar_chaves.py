# Geração de chaves privadas RSA por serviço e distribuição somente das chaves públicas.

# Importa geração e leitura de chaves RSA em formato PEM.
from Crypto.PublicKey import RSA

# Importa assinaturas RSA e política de produtores autorizados.
from comum.seguranca import RAIZ, SERVICOS

# Gera chaves privadas ausentes e distribui públicas para os cinco serviços.
def main():

    # Prepara chaves públicas dos produtores para esta etapa.
    publicas = {}

    # Percorre SERVICOS para processar cada servico.
    for servico in SERVICOS:

        # Prepara diretório de arquivos para esta etapa.
        pasta = RAIZ / servico / "chaves"

        # Executa pasta.mkdir para concluir esta etapa do processamento.
        pasta.mkdir(parents=True, exist_ok=True)

        # Prepara chave privada RSA para esta etapa.
        privada = pasta / "privada.pem"

        # Confere a condição not privada.exists() antes de executar este bloco.
        if not privada.exists():

            # Grava os bytes da chave PEM no arquivo indicado.
            privada.write_bytes(RSA.generate(2048).export_key())

        # Prepara chave RSA carregada para esta etapa.
        chave = RSA.import_key(privada.read_bytes())

        # Confere a condição not chave.has_private() or chave.size_in_bits() < 2048 antes de executar este bloco.
        if not chave.has_private() or chave.size_in_bits() < 2048:

            # Interrompe a operação com erro: .
            raise ValueError(f"Chave privada inválida em {servico}.")

        # Atualiza publicas[servico] com o valor usado por este cenário.
        publicas[servico] = chave.public_key().export_key()

    # Percorre SERVICOS para processar cada destinatario.
    for destinatario in SERVICOS:

        # Prepara diretório de arquivos para esta etapa.
        pasta = RAIZ / destinatario / "chaves" / "publicas"

        # Executa pasta.mkdir para concluir esta etapa do processamento.
        pasta.mkdir(parents=True, exist_ok=True)

        # Percorre publicas.items() para processar cada (produtor, chave).
        for produtor, chave in publicas.items():

            # Grava os bytes da chave PEM no arquivo indicado.
            (pasta / f"{produtor}.pem").write_bytes(chave)

    # Mostra a etapa da demonstração no terminal ou arquivo de log do serviço.
    print("Chaves prontas. Chaves privadas existentes foram preservadas.", flush=True)

# Executa a entrada do serviço somente quando este módulo é iniciado diretamente.
if __name__ == "__main__":

    # Executa main para concluir esta etapa do processamento.
    main()
