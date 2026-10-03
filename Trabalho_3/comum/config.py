# Configuração por variáveis de ambiente, com valores padrão para a demonstração local.

# Importa leitura do ambiente e identificação do sistema operacional.
import os

# Importa caminhos de arquivo portáveis por meio de Path.
from pathlib import Path

# Importa carregamento das configurações opcionais do arquivo .env.
from dotenv import load_dotenv

# Prepara pasta raiz do trabalho para esta etapa.
RAIZ = Path(__file__).resolve().parents[1]

# Carrega o arquivo .env sem sobrescrever variáveis já definidas no ambiente.
load_dotenv(RAIZ / ".env", override=False)

# Prepara diretório de bancos e logs para esta etapa.
DADOS = Path(os.environ.get("DATA_DIR", str(RAIZ / "dados")))

# Prepara endereço REST do Estoque para esta etapa.
ESTOQUE_URL = os.environ.get("ESTOQUE_URL", "http://127.0.0.1:8001")

# Prepara endereço interno do Mock para esta etapa.
MOCK_URL = os.environ.get("MOCK_URL", "http://127.0.0.1:8003")

# Prepara endereço do checkout acessível ao navegador para esta etapa.
MOCK_PUBLIC_URL = os.environ.get("MOCK_PUBLIC_URL", "http://localhost:8003")

# Prepara endereço de retorno HTTP do Pagamento para esta etapa.
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "http://127.0.0.1:8002/webhook")

# Prepara segredo compartilhado do webhook para esta etapa.
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "segredo-local-trabalho3")
