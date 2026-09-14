"""Teste com RabbitMQ real. Encerre todos os serviços antes de executar."""
import json
import os
import re
import subprocess
import sys
import threading
import time
import unittest
from uuid import uuid4

from comum.mensageria import Publicador, publicar_corpo
from comum.seguranca import RAIZ, serializar
from principal.modelo import Principal
from scripts.gerar_chaves import main as gerar_chaves
from scripts.preparar_filas import preparar


class Processo:
    def __init__(self, modulo, *args, **ambiente):
        self.linhas = []
        self.condicao = threading.Condition()
        env = {**os.environ, "PYTHONUTF8": "1", **ambiente}
        self.processo = subprocess.Popen(
            [sys.executable, "-u", "-m", modulo, *args], cwd=RAIZ, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.thread = threading.Thread(target=self._ler, daemon=True)
        self.thread.start()

    def _ler(self):
        for linha in self.processo.stdout:
            with self.condicao:
                self.linhas.append(linha.rstrip())
                self.condicao.notify_all()

    def esperar(self, trecho, timeout=15):
        fim = time.monotonic() + timeout
        with self.condicao:
            while time.monotonic() < fim:
                for linha in self.linhas:
                    if trecho in linha:
                        return linha
                if self.processo.poll() is not None:
                    break
                self.condicao.wait(min(0.2, max(0, fim - time.monotonic())))
        raise AssertionError(f"Não apareceu {trecho!r}. Saída:\n" + "\n".join(self.linhas))

    def enviar(self, texto):
        self.processo.stdin.write(texto)
        self.processo.stdin.flush()

    def fechar(self):
        if self.processo.poll() is None:
            self.processo.terminate()
            try:
                self.processo.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.processo.kill()
                self.processo.wait(timeout=5)
        self.thread.join(timeout=2)
        self.processo.stdin.close()
        self.processo.stdout.close()


class IntegracaoTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        gerar_chaves()
        preparar(limpar=True)

    def setUp(self):
        preparar(limpar=True)
        self.processos = []

    def tearDown(self):
        for processo in reversed(self.processos):
            processo.fechar()
        # Aguarda o broker observar o fechamento dos consumidores antes da próxima sessão.
        fim = time.monotonic() + 5
        while True:
            try:
                preparar(limpar=True)
                break
            except RuntimeError:
                if time.monotonic() >= fim:
                    raise
                time.sleep(0.1)

    def iniciar(self, modulo, *args, **ambiente):
        processo = Processo(modulo, *args, **ambiente)
        self.processos.append(processo)
        nome = args[0] if modulo == "consumidores" else modulo
        processo.esperar(f"PRONTO {nome}")
        return processo

    def fluxo(self, probabilidade):
        estoque = self.iniciar("estoque")
        self.iniciar("pagamento", PROB_APROVACAO=str(probabilidade))
        self.iniciar("entrega")
        principal = self.iniciar("principal")
        principal.enviar("Teste\n")
        principal.esperar("1 Produtos")
        return principal, estoque

    def criar(self, principal, itens):
        inicio = len(principal.linhas)
        principal.enviar(f"2\n{itens}\n")
        fim = time.monotonic() + 15
        while time.monotonic() < fim:
            for linha in principal.linhas[inicio:]:
                resultado = re.search(r"CRIADO ([0-9a-f-]{36})", linha)
                if resultado:
                    return resultado.group(1)
            time.sleep(0.05)
        self.fail("Pedido não criado: " + "\n".join(principal.linhas))

    def test_aprovacao_menu_ativo_exclusao_e_falta_de_estoque(self):
        principal, estoque = self.fluxo(1)
        self.iniciar("consumidores", "c1")
        c2 = self.iniciar("consumidores", "c2")
        self.iniciar("promocoes", INTERVALO_PROMOCOES="0.1")
        c2.esperar("PROMOCAO c2")
        # Os sete processos coexistem: promoções continuam durante o fluxo de pedidos.
        pedido_id = self.criar(principal, "1:2")
        # Nenhuma entrada adicional: o consumidor atualiza enquanto o menu espera input().
        principal.esperar(f"STATUS {pedido_id} enviado")
        principal.enviar("4\n")
        principal.esperar(f"{pedido_id} | enviado")
        principal.enviar(f"3\n{pedido_id}\n")
        estoque.esperar(f"DEVOLUCAO {pedido_id} {{'1': 2}} SALDOS {{'1': 10")
        indisponivel = self.criar(principal, "1:11")
        principal.esperar(f"STATUS {indisponivel} excluido estoque.indisponivel")
        estoque.esperar(f"DEVOLUCAO {indisponivel} {{}} SALDOS {{'1': 10")

    def test_recusa_restitui_reserva(self):
        principal, estoque = self.fluxo(0)
        pedido_id = self.criar(principal, "1:2,2:1")
        principal.esperar(f"STATUS {pedido_id} excluido pagamento.recusado")
        estoque.esperar(f"DEVOLUCAO {pedido_id} {{'1': 2, '2': 1}} SALDOS {{'1': 10, '2': 10")

    def test_assinatura_invalida_descartada_e_repeticao_ignorada(self):
        estoque = self.iniciar("estoque")
        publicador = Publicador("principal")
        try:
            tipo, dados = Principal().criar("Teste", [("1", 2)])
            valido = publicador.assinador.assinar(tipo, dados)
            adulterado = json.loads(valido)
            adulterado["data"]["cliente"] = "Adulterado"
            publicar_corpo(publicador.canal, tipo, serializar(adulterado))
            estoque.esperar("DESCARTADO pedido.criado")
            # Mesmo assinado por um produtor conhecido, conteúdo inválido é descartado.
            malformado = json.loads(valido)["data"]
            malformado["itens"][0]["produto_id"] = []
            publicador.publicar(tipo, malformado)
            publicar_corpo(publicador.canal, tipo, valido)
            publicar_corpo(publicador.canal, tipo, valido)
            estoque.esperar(f"RESERVA {dados['pedido_id']}")
            publicador.publicar("pedido.excluido", {"pedido_id": dados["pedido_id"]})
            estoque.esperar(f"DEVOLUCAO {dados['pedido_id']} {{'1': 2}} SALDOS {{'1': 10")
            self.assertEqual(sum(f"RESERVA {dados['pedido_id']}" in l for l in estoque.linhas), 1)
            self.assertEqual(sum("DESCARTADO pedido.criado" in l for l in estoque.linhas), 2)
        finally:
            publicador.fechar()

    def test_principal_descarta_id_invalido_e_continua_consumindo(self):
        principal = self.iniciar("principal")
        principal.enviar("Teste\n")
        principal.esperar("1 Produtos")
        publicador = Publicador("entrega")
        try:
            publicador.publicar("pedido.enviado", {"pedido_id": []})
            principal.esperar("DESCARTADO pedido.enviado")
            pedido_id = self.criar(principal, "1:1")
            publicador.publicar("pedido.enviado", {"pedido_id": pedido_id, "nota_id": "teste"})
            principal.esperar(f"STATUS {pedido_id} enviado")
        finally:
            publicador.fechar()

    def test_promocoes_aleatorias_e_bindings_c1_c2(self):
        c1 = self.iniciar("consumidores", "c1")
        c2 = self.iniciar("consumidores", "c2")
        promocoes = self.iniciar("promocoes", INTERVALO_PROMOCOES="0.1")
        promocoes.esperar("PUBLICADO promocao.categoria.")
        c2.esperar("PROMOCAO c2")
        publicador = Publicador("promocoes")
        try:
            for categoria in "ABC":
                marcador = str(uuid4())
                tipo = f"promocao.categoria.{categoria}"
                publicador.publicar(tipo, {"teste": marcador, "categoria": categoria})
                c2.esperar(marcador)
                if categoria in "AB":
                    c1.esperar(marcador)
                else:
                    # A mensagem A posterior funciona como barreira na fila de C1.
                    barreira = str(uuid4())
                    publicador.publicar("promocao.categoria.A", {"teste": barreira})
                    c1.esperar(barreira)
                    self.assertFalse(any(marcador in l for l in c1.linhas))
        finally:
            publicador.fechar()


if __name__ == "__main__":
    unittest.main(verbosity=2)
