import base64
import binascii
import json
from pathlib import Path
from uuid import uuid4

from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

RAIZ = Path(__file__).resolve().parents[1]
SERVICOS = ("principal", "estoque", "pagamento", "entrega", "promocoes")
PRODUTORES = {
    "pedido.criado": "principal", "pedido.excluido": "principal",
    "pedido.estoque_ok": "estoque", "estoque.indisponivel": "estoque",
    "pagamento.aprovado": "pagamento", "pagamento.recusado": "pagamento",
    "pedido.enviado": "entrega",
    **{f"promocao.categoria.{c}": "promocoes" for c in "ABC"},
}


def serializar(conteudo):
    return json.dumps(conteudo, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


class Assinador:
    def __init__(self, produtor, privada, publicas):
        self.produtor = produtor
        self.privada = privada
        self.publicas = publicas

    @classmethod
    def carregar(cls, servico):
        pasta = RAIZ / ("consumidores" if servico in ("c1", "c2") else servico) / "chaves"
        try:
            privada = RSA.import_key((pasta / "privada.pem").read_bytes()) if servico in SERVICOS else None
            publicas = {p.stem: RSA.import_key(p.read_bytes())
                        for p in (pasta / "publicas").glob("*.pem")}
            exigidas = set(SERVICOS) if servico in SERVICOS else {"promocoes"}
            if not exigidas.issubset(publicas):
                raise FileNotFoundError("Faltam chaves públicas.")
        except (OSError, ValueError) as erro:
            raise RuntimeError("Prepare as chaves: python -m scripts.gerar_chaves") from erro
        return cls(servico, privada, publicas)

    def assinar(self, tipo, dados):
        if PRODUTORES.get(tipo) != self.produtor or self.privada is None:
            raise ValueError("Produtor não autorizado para este evento.")
        envelope = {"event_id": str(uuid4()), "producer": self.produtor,
                    "event_type": tipo, "data": dados}
        assinatura = pkcs1_15.new(self.privada).sign(SHA256.new(serializar(envelope)))
        envelope["Signature"] = base64.b64encode(assinatura).decode("ascii")
        return serializar(envelope)

    def verificar(self, corpo, routing_key):
        try:
            envelope = json.loads(corpo)
            campos = {"event_id", "producer", "event_type", "data", "Signature"}
            if not isinstance(envelope, dict) or set(envelope) != campos:
                raise ValueError("Envelope inválido.")
            if not isinstance(envelope["event_id"], str) or not envelope["event_id"]:
                raise ValueError("event_id inválido.")
            if not isinstance(envelope["data"], dict):
                raise ValueError("Dados inválidos.")
            produtor = envelope["producer"]
            if envelope["event_type"] != routing_key or PRODUTORES.get(routing_key) != produtor:
                raise ValueError("Produtor ou routing key incorretos.")
            assinatura = base64.b64decode(envelope["Signature"], validate=True)
            conteudo = {k: v for k, v in envelope.items() if k != "Signature"}
            pkcs1_15.new(self.publicas[produtor]).verify(SHA256.new(serializar(conteudo)), assinatura)
            return envelope
        except (ValueError, TypeError, KeyError, UnicodeError, binascii.Error) as erro:
            raise ValueError("Evento rejeitado: assinatura, produtor ou envelope inválido.") from erro
