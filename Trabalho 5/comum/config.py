import os
from pathlib import Path
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]

# Carrega variáveis do .env sem sobrescrever as já existentes no ambiente
load_dotenv(RAIZ / ".env", override=False)

DADOS = Path(os.environ.get("DATA_DIR", str(RAIZ / "dados")))
ESTOQUE_URL = os.environ.get("ESTOQUE_URL", "http://127.0.0.1:8001")
MOCK_URL = os.environ.get("MOCK_URL", "http://127.0.0.1:8003")
MOCK_PUBLIC_URL = os.environ.get("MOCK_PUBLIC_URL", "http://localhost:8003")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "http://127.0.0.1:8002/webhook")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "segredo-local-trabalho3")
