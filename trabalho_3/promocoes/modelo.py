from uuid import UUID
from email_validator import EmailNotValidError, validate_email

from comum.banco import json_texto


class Promocoes:
    """Persiste interesses e o histórico de envios promocionais."""

    def __init__(self, banco):
        self.banco = banco
        banco.schema("""
            CREATE TABLE IF NOT EXISTS interesses (
                cliente TEXT PRIMARY KEY, email TEXT, categorias TEXT, versao INTEGER);
            CREATE TABLE IF NOT EXISTS envios (
                id TEXT PRIMARY KEY, email TEXT, assunto TEXT, texto TEXT,
                modo TEXT, enviado_em TEXT DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')));
        """)

    def tratar(self, con, tipo, dados):
        """Valida o cadastro e aceita apenas versões mais recentes do interesse."""
        try:
            cliente = str(UUID(dados["cliente"]))
            email = validate_email(dados["email"], check_deliverability=False).normalized
            cats = dados["categorias"]
            versao = dados["versao"]

            if not isinstance(cats, list) or not all(
                isinstance(c, str) and c in "ABC" and len(c) == 1 for c in cats
            ):
                raise ValueError("Categorias inválidas")

            if type(versao) is not int or versao < 1:
                raise ValueError("Versão inválida")

        except (KeyError, TypeError, AttributeError, EmailNotValidError) as erro:
            raise ValueError("Interesse inválido") from erro

        # Atualiza o cadastro apenas se a versão recebida for mais recente
        con.execute(
            "INSERT INTO interesses VALUES (?,?,?,?) ON CONFLICT(cliente) DO UPDATE SET "
            "email=excluded.email,categorias=excluded.categorias,versao=excluded.versao "
            "WHERE excluded.versao > interesses.versao",
            (cliente, email, json_texto(sorted(set(cats))), versao),
        )
        return []
