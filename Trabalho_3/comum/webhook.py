# Autenticação do webhook externo por HMAC-SHA256 e janela de validade de cinco minutos.

# Importa algoritmos de resumo criptográfico, aqui SHA-256.
import hashlib

# Importa assinatura com segredo compartilhado e comparação resistente a diferenças de tempo.
import hmac

# Importa relógios, timestamps e pausas do agendamento e dos testes.
import time

# Importa configurações compartilhadas, como URLs e caminho dos dados.
from comum.config import WEBHOOK_SECRET

# Assina timestamp e corpo original com HMAC-SHA256 usando o segredo compartilhado.
def assinar_webhook(corpo, timestamp):

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return hmac.new(

        # Fornece os valores desta linha à chamada ou expressão iniciada acima.
        WEBHOOK_SECRET.encode(), timestamp.encode() + b"." + corpo, hashlib.sha256

    # Fornece os valores desta linha à chamada ou expressão iniciada acima.
    ).hexdigest()

# Confere a assinatura e rejeita timestamps com diferença superior a cinco minutos.
def verificar_webhook(corpo, timestamp, assinatura):

    # Executa operações que podem falhar e encaminha os erros ao tratamento correspondente.
    try:

        # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
        return abs(time.time() - int(timestamp)) <= 300 and hmac.compare_digest(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            assinar_webhook(corpo, timestamp), assinatura

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

    # Trata (ValueError, TypeError) sem confundir falha com resultado válido.
    except (ValueError, TypeError):

        # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
        return False
