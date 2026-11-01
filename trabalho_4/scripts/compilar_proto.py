"""Compila arquivos .proto e ajusta imports para módulos Python."""

from pathlib import Path
import sys
from grpc_tools import protoc

RAIZ = Path(__file__).resolve().parents[1]
PROTO_DIR = RAIZ / "protos"
SAIDA_DIR = RAIZ / "comum" / "proto"


def compilar():
    SAIDA_DIR.mkdir(parents=True, exist_ok=True)

    proto_files = list(PROTO_DIR.glob("*.proto"))
    if not proto_files:
        raise FileNotFoundError(f"Nenhum arquivo .proto encontrado em {PROTO_DIR}")

    for proto in proto_files:
        print(f"Compilando {proto.name}...")
        args = [
            "protoc",
            f"-I{PROTO_DIR}",
            f"--python_out={SAIDA_DIR}",
            f"--grpc_python_out={SAIDA_DIR}",
            str(proto),
        ]
        ret = protoc.main(args)
        if ret != 0:
            sys.exit(f"Erro ao compilar {proto.name} (código {ret})")

    # Ajusta importação absoluta para relativa em arquivos _grpc.py
    for grpc_file in SAIDA_DIR.glob("*_pb2_grpc.py"):
        conteudo = grpc_file.read_text(encoding="utf-8")
        corrigido = conteudo.replace(
            "import cluster_pb2 as cluster__pb2",
            "from . import cluster_pb2 as cluster__pb2",
        )
        grpc_file.write_text(corrigido, encoding="utf-8")

    print(f"Arquivos gRPC gerados com sucesso em {SAIDA_DIR}")


if __name__ == "__main__":
    compilar()

