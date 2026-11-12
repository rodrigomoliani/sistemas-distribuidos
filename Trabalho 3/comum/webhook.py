import hashlib
import hmac
import time

from comum.config import WEBHOOK_SECRET


def assinar_webhook(corpo: bytes, timestamp: str) -> str:
    """Assina timestamp e corpo com HMAC-SHA256 usando o segredo compartilhado."""
    return hmac.new(
        WEBHOOK_SECRET.encode(), timestamp.encode() + b"." + corpo, hashlib.sha256
    ).hexdigest()


def verificar_webhook(corpo: bytes, timestamp: str, assinatura: str) -> bool:
    """Verifica assinatura HMAC e rejeita requisições com timestamp fora da janela de 5 minutos."""
    try:
        if abs(time.time() - int(timestamp)) > 300:
            return False
        return hmac.compare_digest(assinar_webhook(corpo, timestamp), assinatura)
    except (ValueError, TypeError):
        return False
