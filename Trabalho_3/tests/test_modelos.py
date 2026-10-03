# Testes das regras de negócio: reservas, cancelamentos, cobranças, histórico e persistência.

# Importa conversão entre objetos Python e texto JSON.
import json

# Importa diretórios temporários usados para isolar os bancos dos testes.
import tempfile

# Importa estrutura de testes, asserções e execução automática dos casos.
import unittest

# Importa caminhos de arquivo portáveis por meio de Path.
from pathlib import Path

# Importa objetos simples que simulam respostas e componentes nos testes.
from types import SimpleNamespace

# Importa substituições temporárias de dependências, sem acesso a serviços reais.
from unittest.mock import patch

# Importa identificadores UUID para clientes, pedidos, eventos, cobranças ou campanhas.
from uuid import uuid4

# Importa banco local, serialização JSON e gravação atômica de eventos na outbox.
from comum.banco import Banco, json_texto

# Importa catálogo inicial, valores em centavos e validação de itens e totais.
from comum.catalogo import montar_itens

# Importa modelo com as regras de negócio do microsserviço estoque.
from estoque.modelo import Estoque

# Importa modelo com as regras de negócio do microsserviço entrega.
from entrega.modelo import Entrega

# Importa modelo com as regras de negócio do microsserviço pagamento.
from pagamento.modelo import Pagamento

# Importa modelo com as regras de negócio do microsserviço principal.
from principal.modelo import Principal

# Importa modelo com as regras de negócio do microsserviço promocoes.
from promocoes.modelo import Promocoes

# Consulta um pedido do cliente; nos testes, monta um pedido válido de demonstração.
def pedido(q=2, produto="1"):

    # Prepara itens do pedido para esta etapa.
    itens = montar_itens([(produto, q)])

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return {

        # Define o campo pedido_id desta estrutura de dados.
        "pedido_id": str(uuid4()),

        # Define o campo cliente desta estrutura de dados.
        "cliente": str(uuid4()),

        # Define o campo nome desta estrutura de dados.
        "nome": "Ana",

        # Define o campo itens desta estrutura de dados.
        "itens": itens,

        # Define o campo total_centavos desta estrutura de dados.
        "total_centavos": sum(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            i["quantidade"] * i["preco_unitario_centavos"] for i in itens

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        ),

    # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
    }

# Agrupa os testes relacionados a Regras.
class Regras(unittest.TestCase):

    # Prepara recursos novos e isolados antes de cada teste.
    def setUp(self):

        # Guarda o banco exclusivo do serviço ou cria um banco isolado para o teste.
        self.banco = Banco("teste", ":memory:")

    # Libera recursos e desfaz substituições após cada teste.
    def tearDown(self):

        # Libera o recurso do serviço depois do processamento.
        self.banco.fechar()

    # Define a operação tratar.
    def tratar(self, modelo, tipo, dados):

        # Executa este bloco na mesma transação SQLite, com confirmação ou desfazimento automático.
        with self.banco.transacao() as con:

            # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
            return modelo.tratar(con, tipo, dados)

    # Testa o cenário de reserva e devolucao unica.
    def test_reserva_e_devolucao_unica(self):

        # Prepara os recursos indicados para serem usados juntos nesta etapa.
        e, p = Estoque(self.banco), pedido()

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(self.tratar(e, "pedido.criado", p)[0][0], "pedido.estoque_ok")

        # Executa self.tratar para concluir esta etapa do processamento.
        self.tratar(e, "pedido.criado", p)

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(e.produtos()[0]["quantidade"], 8)

        # Executa self.tratar para concluir esta etapa do processamento.
        self.tratar(e, "pedido.excluido", {"pedido_id": p["pedido_id"]})

        # Executa self.tratar para concluir esta etapa do processamento.
        self.tratar(e, "pedido.excluido", {"pedido_id": p["pedido_id"]})

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(e.produtos()[0]["quantidade"], 10)

    # Testa o cenário de sem reserva parcial.
    def test_sem_reserva_parcial(self):

        # Prepara os recursos indicados para serem usados juntos nesta etapa.
        e, p = Estoque(self.banco), pedido()

        # Atualiza p['itens'] com o valor usado por este cenário.
        p["itens"] = montar_itens([("1", 1), ("2", 11)])

        # Atualiza p['total_centavos'] com o valor usado por este cenário.
        p["total_centavos"] = sum(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            i["quantidade"] * i["preco_unitario_centavos"] for i in p["itens"]

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            self.tratar(e, "pedido.criado", p)[0][0], "estoque.indisponivel"

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual([p["quantidade"] for p in e.produtos()], [10, 10, 10])

    # Testa o cenário de exclusao antes da criacao.
    def test_exclusao_antes_da_criacao(self):

        # Prepara os recursos indicados para serem usados juntos nesta etapa.
        e, p = Estoque(self.banco), pedido()

        # Executa self.tratar para concluir esta etapa do processamento.
        self.tratar(e, "pedido.excluido", {"pedido_id": p["pedido_id"]})

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(self.tratar(e, "pedido.criado", p), [])

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(e.produtos()[0]["quantidade"], 10)

    # Testa o cenário de persistencia estoque.
    def test_persistencia_estoque(self):

        # Abre o contexto tempfile.TemporaryDirectory() e garante sua finalização ao sair do bloco.
        with tempfile.TemporaryDirectory() as pasta:

            # Prepara caminho do banco ou arquivo para esta etapa.
            arquivo = Path(pasta) / "estoque.sqlite3"

            # Prepara b para esta etapa.
            b = Banco("estoque", arquivo)

            # Prepara e para esta etapa.
            e = Estoque(b)

            # Executa este bloco na mesma transação SQLite, com confirmação ou desfazimento automático.
            with b.transacao() as con:

                # Executa e.tratar para concluir esta etapa do processamento.
                e.tratar(con, "pedido.criado", pedido())

            # Libera o recurso do serviço depois do processamento.
            b.fechar()

            # Prepara b para esta etapa.
            b = Banco("estoque", arquivo)

            # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
            self.assertEqual(Estoque(b).produtos()[0]["quantidade"], 8)

            # Libera o recurso do serviço depois do processamento.
            b.fechar()

    # Testa o cenário de preco adulterado.
    def test_preco_adulterado(self):

        # Prepara os recursos indicados para serem usados juntos nesta etapa.
        e, p = Estoque(self.banco), pedido()

        # Atualiza p['total_centavos'] com o valor usado por este cenário.
        p["total_centavos"] = 1

        # Exige que este bloco levante a exceção esperada pelo teste.
        with self.assertRaises(ValueError):

            # Executa self.tratar para concluir esta etapa do processamento.
            self.tratar(e, "pedido.criado", p)

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(e.produtos()[0]["quantidade"], 10)

    # Testa o cenário de nota idempotente.
    def test_nota_idempotente(self):

        # Prepara os recursos indicados para serem usados juntos nesta etapa.
        e, p = Entrega(self.banco), pedido()

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            self.tratar(e, "pagamento.aprovado", p)[0][0], "pedido.enviado"

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(self.tratar(e, "pagamento.aprovado", p), [])

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(len(self.banco.ler("SELECT * FROM notas")), 1)

    # Insere um pedido inicial no banco em memória para testar os estados do Gateway.
    def criar_principal(self):

        # Prepara os recursos indicados para serem usados juntos nesta etapa.
        modelo, p = Principal(self.banco), pedido()

        # Executa este bloco na mesma transação SQLite, com confirmação ou desfazimento automático.
        with self.banco.transacao() as con:

            # Insere o registro em pedidos; conflitos são tratados conforme a instrução.
            con.execute(

                # Insere o registro em pedidos; conflitos são tratados conforme a instrução.
                "INSERT INTO pedidos(id,cliente,dados,estado) VALUES (?,?,?,?)",

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                (p["pedido_id"], p["cliente"], json_texto(p), "Pedido Criado"),

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            )

        # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
        return modelo, p

    # Testa o cenário de eventos atrasados nao regridem.
    def test_eventos_atrasados_nao_regridem(self):

        # Prepara os recursos indicados para serem usados juntos nesta etapa.
        m, p = self.criar_principal()

        # Executa self.tratar para concluir esta etapa do processamento.
        self.tratar(m, "pedido.enviado", {"pedido_id": p["pedido_id"], "nota_id": "nf"})

        # Executa self.tratar para concluir esta etapa do processamento.
        self.tratar(m, "pagamento.aprovado", p)

        # Executa self.tratar para concluir esta etapa do processamento.
        self.tratar(m, "pedido.estoque_ok", p)

        # Prepara r para esta etapa.
        r = m.consultar(p["cliente"])[0]

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(r["estado"], "Pedido Enviado")

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(len(r["historico"]), 3)

    # Testa o cenário de recusa gera exclusao.
    def test_recusa_gera_exclusao(self):

        # Prepara os recursos indicados para serem usados juntos nesta etapa.
        m, p = self.criar_principal()

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            self.tratar(m, "pagamento.recusado", p)[0][0], "pedido.excluido"

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            self.tratar(

                # Fornece os valores desta linha à chamada ou expressão iniciada acima.
                m, "pedido.enviado", {"pedido_id": p["pedido_id"], "nota_id": "nf"}

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            ),

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            [],

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(m.consultar(p["cliente"])[0]["estado"], "Pagamento Recusado")

    # Testa o cenário de interesse cancelamento e evento atrasado.
    def test_interesse_cancelamento_e_evento_atrasado(self):

        # Prepara os recursos indicados para serem usados juntos nesta etapa.
        m, cid = Promocoes(self.banco), str(uuid4())

        # Prepara dados da operação para esta etapa.
        dados = {

            # Define o campo cliente desta estrutura de dados.
            "cliente": cid,

            # Define o campo email desta estrutura de dados.
            "email": "ana@example.com",

            # Define o campo categorias desta estrutura de dados.
            "categorias": ["A", "B"],

            # Define o campo versao desta estrutura de dados.
            "versao": 1,

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        }

        # Executa self.tratar para concluir esta etapa do processamento.
        self.tratar(m, "interesse.promocao", dados)

        # Executa self.tratar para concluir esta etapa do processamento.
        self.tratar(m, "interesse.promocao", {**dados, "categorias": [], "versao": 2})

        # Executa self.tratar para concluir esta etapa do processamento.
        self.tratar(m, "interesse.promocao", dados)

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(

            # Fornece os valores desta linha à chamada ou expressão iniciada acima.
            json.loads(self.banco.ler("SELECT * FROM interesses")[0]["categorias"]), []

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

    # Testa o cenário de checkout idempotente e webhook.
    def test_checkout_idempotente_e_webhook(self):

        # Prepara os recursos indicados para serem usados juntos nesta etapa.
        m, p = Pagamento(self.banco), pedido()

        # Prepara resposta recebida ou simulada para esta etapa.
        resposta = SimpleNamespace(

            # Define o argumento ou campo raise_for_status desta operação.
            raise_for_status=lambda: None,

            # Envia estes dados como corpo JSON da requisição HTTP.
            json=lambda: {

                # Define o campo id desta estrutura de dados.
                "id": "cob1",

                # Define o campo checkout_url desta estrutura de dados.
                "checkout_url": "http://localhost:8003/checkout/cob1",

            # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
            },

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Isola temporariamente a dependência para testar sem chamadas reais ao recurso substituído.
        with patch("pagamento.modelo.httpx.post", return_value=resposta) as chamada:

            # Executa self.tratar para concluir esta etapa do processamento.
            self.tratar(m, "pedido.estoque_ok", p)

            # Executa self.tratar para concluir esta etapa do processamento.
            self.tratar(m, "pedido.estoque_ok", p)

            # Confere que a dependência simulada foi chamada uma única vez.
            chamada.assert_called_once()

        # Prepara dados validados de entrada para esta etapa.
        entrada = SimpleNamespace(

            # Define o argumento ou campo cobranca_id desta operação.
            cobranca_id="cob1",

            # Define o argumento ou campo pedido_id desta operação.
            pedido_id=p["pedido_id"],

            # Define o argumento ou campo total_centavos desta operação.
            total_centavos=p["total_centavos"],

            # Define o argumento ou campo status desta operação.
            status="APROVADO",

        # Fecha a chamada, coleção ou expressão iniciada nas linhas anteriores.
        )

        # Executa este bloco na mesma transação SQLite, com confirmação ou desfazimento automático.
        with self.banco.transacao() as con:

            # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
            self.assertEqual(m.resultado(con, entrada)[0][0], "pagamento.aprovado")

            # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
            self.assertEqual(m.resultado(con, entrada), [])

            # Prepara entrada.status para esta etapa.
            entrada.status = "RECUSADO"

            # Exige que este bloco levante a exceção esperada pelo teste.
            with self.assertRaises(ValueError):

                # Executa m.resultado para concluir esta etapa do processamento.
                m.resultado(con, entrada)

    # Testa o cenário de transacao desfaz estado e outbox.
    def test_transacao_desfaz_estado_e_outbox(self):

        # Exige que este bloco levante a exceção esperada pelo teste.
        with self.assertRaises(RuntimeError):

            # Executa este bloco na mesma transação SQLite, com confirmação ou desfazimento automático.
            with self.banco.transacao() as con:

                # Insere o registro em outbox; conflitos são tratados conforme a instrução.
                con.execute("INSERT INTO outbox(tipo,corpo) VALUES ('x','y')")

                # Interrompe a operação com erro: Falha simulada.
                raise RuntimeError("Falha simulada")

        # Confere a igualdade entre o resultado obtido e o valor esperado neste cenário.
        self.assertEqual(self.banco.ler("SELECT * FROM outbox"), [])

# Executa a entrada do serviço somente quando este módulo é iniciado diretamente.
if __name__ == "__main__":

    # Executa unittest.main para concluir esta etapa do processamento.
    unittest.main()
