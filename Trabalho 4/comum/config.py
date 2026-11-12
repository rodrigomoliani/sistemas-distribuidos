import os
from pathlib import Path
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parents[1]

# Carrega .env se existir
load_dotenv(RAIZ / ".env", override=False)

NODE_ID = int(os.environ.get("NODE_ID", "1"))
NODE_HOST = os.environ.get("NODE_HOST", "0.0.0.0")
NODE_PORT = int(os.environ.get("NODE_PORT", str(50050 + NODE_ID)))

CLUSTER_SIZE = int(os.environ.get("CLUSTER_SIZE", "4"))
QUORUM_SIZE = (CLUSTER_SIZE // 2) + 1  # Para N=4, Quorum=3

# Mapeamento interno entre os nós (no docker, "no1:50051", localmente "127.0.0.1:50051")
def _parse_peers(env_var_name, padrao_host):
    raw = os.environ.get(env_var_name, "")
    if raw.strip():
        # Formato: "1=no1:50051,2=no2:50052,3=no3:50053,4=no4:50054"
        resultado = {}
        for item in raw.split(","):
            if "=" in item:
                nid, addr = item.split("=", 1)
                resultado[int(nid.strip())] = addr.strip()
        return resultado
    return {i: f"{padrao_host}:{50050 + i}" for i in range(1, CLUSTER_SIZE + 1)}


PEERS = _parse_peers("PEERS", os.environ.get("PEERS_HOST", "127.0.0.1"))
CLIENT_PEERS = _parse_peers("CLIENT_PEERS", os.environ.get("CLIENT_HOST", "127.0.0.1"))

# Diretório de dados do nó
dados_env = os.environ.get("DATA_DIR")
if dados_env:
    DATA_DIR = Path(dados_env)
else:
    DATA_DIR = RAIZ / "dados" / f"no{NODE_ID}"

# Temporizadores (segundos)
FETCH_INTERVAL = float(os.environ.get("FETCH_INTERVAL", "0.1"))        # 100ms
HEARTBEAT_TIMEOUT = float(os.environ.get("HEARTBEAT_TIMEOUT", "0.6"))    # Timeout do líder para considerar réplica inativa
ELECTION_TIMEOUT_MIN = float(os.environ.get("ELECTION_TIMEOUT_MIN", "1.5"))
ELECTION_TIMEOUT_MAX = float(os.environ.get("ELECTION_TIMEOUT_MAX", "3.0"))

