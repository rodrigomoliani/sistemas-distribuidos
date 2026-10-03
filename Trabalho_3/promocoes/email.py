# Adaptador de e-mail: demonstração local ou integração HTTPS real com o Resend.

# Importa leitura do ambiente e identificação do sistema operacional.
import os

# Importa requisições HTTP aos serviços REST e às APIs externas.
import httpx

# Seleciona demonstração em arquivo ou envio real pelo Resend.
class Email:

    # Inicializa o componente e prepara os recursos usados por seus métodos.
    def __init__(self):

        # Seleciona arquivo para demonstração ou resend para o provedor externo.
        self.modo = os.environ.get("EMAIL_MODO", "arquivo")

        # Confere a condição self.modo not in ('arquivo', 'resend') antes de executar este bloco.
        if self.modo not in ("arquivo", "resend"):

            # Interrompe a operação com erro: EMAIL_MODO deve ser arquivo ou resend.
            raise ValueError("EMAIL_MODO deve ser arquivo ou resend")

        # Lê a chave da API Resend das variáveis de ambiente, sem incluí-la no código.
        self.chave = os.environ.get("RESEND_API_KEY", "")

        # Configura o remetente de e-mail, que precisa ser autorizado pelo Resend.
        self.remetente = os.environ.get(

            # Fornece este valor textual à chamada ou coleção em construção.
            "EMAIL_FROM", "E-commerce UTFPR <onboarding@resend.dev>"

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Confere a condição self.modo == 'resend' and (not self.chave) antes de executar este bloco.
        if self.modo == "resend" and not self.chave:

            # Interrompe a operação com erro: Configure RESEND_API_KEY para enviar e-mails reais.
            raise ValueError("Configure RESEND_API_KEY para enviar e-mails reais")

    # Registra a demonstração local ou envia a mensagem à API HTTPS do Resend.
    def enviar(self, destinatario, assunto, texto, envio_id):

        # Confere a condição self.modo == 'arquivo' antes de executar este bloco.
        if self.modo == "arquivo":

            # Mostra a etapa da demonstração no terminal ou arquivo de log do serviço.
            print(f"EMAIL_DEMONSTRACAO {destinatario}: {assunto} | {texto}", flush=True)

            # Encerra esta operação sem produzir um valor de retorno.
            return

        # Prepara r para esta etapa.
        r = httpx.post(

            # Fornece este valor textual à chamada ou coleção em construção.
            "https://api.resend.com/emails",

            # Limita a duração da operação para que uma falha de rede não bloqueie indefinidamente.
            timeout=8,

            # Define os headers HTTP de formato, cache ou autenticação desta requisição.
            headers={

                # Define o campo Authorization desta estrutura de dados.
                "Authorization": f"Bearer {self.chave}",

                # Define o campo Idempotency-Key desta estrutura de dados.
                "Idempotency-Key": envio_id,

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            },

            # Envia estes dados como corpo JSON da requisição HTTP.
            json={

                # Define o campo from desta estrutura de dados.
                "from": self.remetente,

                # Define o campo to desta estrutura de dados.
                "to": [destinatario],

                # Define o campo subject desta estrutura de dados.
                "subject": assunto,

                # Define o campo text desta estrutura de dados.
                "text": texto,

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            },

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Transforma respostas HTTP de erro em exceções, evitando tratar falha como sucesso.
        r.raise_for_status()
