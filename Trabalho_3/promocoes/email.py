import os
import httpx


class Email:
    """Adaptador de e-mail: suporta demonstração local (arquivo) ou envio real HTTPS (Resend)."""

    def __init__(self):
        self.modo = os.environ.get("EMAIL_MODO", "arquivo")
        if self.modo not in ("arquivo", "resend"):
            raise ValueError("EMAIL_MODO deve ser arquivo ou resend")

        self.chave = os.environ.get("RESEND_API_KEY", "")
        self.remetente = os.environ.get("EMAIL_FROM", "E-commerce UTFPR <onboarding@resend.dev>")

        if self.modo == "resend" and not self.chave:
            raise ValueError("Configure RESEND_API_KEY para enviar e-mails reais")

    def enviar(self, destinatario, assunto, texto, envio_id):
        """Registra a demonstração local em log/banco ou dispara via API do Resend."""
        if self.modo == "arquivo":
            print(f"EMAIL_DEMONSTRACAO {destinatario}: {assunto} | {texto}", flush=True)
            return

        r = httpx.post(
            "https://api.resend.com/emails",
            timeout=8,
            headers={
                "Authorization": f"Bearer {self.chave}",
                "Idempotency-Key": envio_id,
            },
            json={
                "from": self.remetente,
                "to": [destinatario],
                "subject": assunto,
                "text": texto,
            },
        )
        r.raise_for_status()
