# Roteiro automatizado com broker real e processos separados.
# Use uma sessão dedicada: este teste prepara chaves e limpa as seis filas.
# O controlador usa stdin/stdout para simular o usuário e observar resultados;
# a comunicação de negócio entre os serviços continua passando pelo RabbitMQ.
# [AMQP VIA COMUM] marca os pontos que publicam ou administram o broker.

"""Teste com RabbitMQ real. Encerre todos os serviços antes de executar."""

# Lê envelopes JSON para criar mensagens adulteradas de teste.
import json

# Obtém o ambiente que será herdado pelos processos filhos.
import os

# Usa expressão regular para extrair IDs impressos pelo menu.
import re

# Inicia e encerra processos Python reais da aplicação.
import subprocess

# sys.executable identifica o mesmo interpretador que executa o teste.
import sys

# Cria threads de leitura e uma Condition para avisar sobre novas linhas.
import threading

# Fornece relógio monotônico e pequenas pausas durante as esperas.
import time

# Organiza cenários, preparação, limpeza e asserções do teste de integração.
import unittest

# Cria marcadores únicos para distinguir mensagens do teste das promoções aleatórias.
from uuid import uuid4

# Reutiliza o publicador real; publicar_corpo também permite enviar bytes
# adulterados sem gerar automaticamente uma assinatura nova.
from comum.mensageria import Publicador, publicar_corpo

# RAIZ indica onde iniciar os módulos; serializar reproduz o formato do envelope.
from comum.seguranca import RAIZ, serializar

# Usa o modelo local só para montar dados válidos em cenários controlados.
from principal.modelo import Principal

# Importa main do gerador com nome explícito para preparar as chaves do teste.
from scripts.gerar_chaves import main as gerar_chaves

# Reutiliza preparação/limpeza de filas via AMQP, sem API HTTP administrativa.
from scripts.preparar_filas import preparar


# Encapsula um processo real, sua entrada padrão e o histórico da saída.
class Processo:

    # modulo escolhe o programa; *args reúne argumentos posicionais;
    # **ambiente reúne variáveis extras que controlam a simulação.
    def __init__(self, modulo, *args, **ambiente):

        # Histórico de linhas do terminal desse processo, usado nas verificações.
        self.linhas = []

        # Condition combina lock e espera/notificação entre leitor e teste.
        self.condicao = threading.Condition()

        # Copia o ambiente, força UTF-8 e aplica as substituições específicas do cenário.
        env = {**os.environ, "PYTHONUTF8": "1", **ambiente}

        # Inicia o programa filho sem esperar que ele termine.
        self.processo = subprocess.Popen(

            # Mesmo Python do teste; -u evita buffer; -m executa o módulo.
            # Usa RAIZ como diretório atual e o ambiente preparado.
            [sys.executable, "-u", "-m", modulo, *args], cwd=RAIZ, env=env,

            # Pipes permitem simular o teclado e ler a saída; erros vão para o mesmo fluxo
            # que stdout, facilitando diagnóstico quando um processo falha.
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,

            # Decodifica o fluxo como texto UTF-8; no Windows, evita abrir janela visível.
            # getattr usa zero como alternativa em plataformas sem CREATE_NO_WINDOW.
            text=True, encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        # Prepara thread que drena stdout para não bloquear o processo filho.
        self.thread = threading.Thread(target=self._ler, daemon=True)

        # Inicia a leitura em paralelo aos comandos e esperas do teste.
        self.thread.start()

    # Alvo da thread de leitura; roda enquanto o fluxo de saída produzir linhas.
    def _ler(self):

        # Lê stdout linha a linha; encerra quando o pipe chegar ao fim.
        for linha in self.processo.stdout:

            # Adquire o lock da Condition ao modificar o histórico.
            with self.condicao:

                # Guarda a linha removendo caracteres em branco ao final.
                self.linhas.append(linha.rstrip())

                # Acorda quem estiver esperando uma linha aparecer; não publica evento AMQP.
                self.condicao.notify_all()

    # Espera um trecho de texto aparecer no histórico, por padrão até 15 segundos.
    def esperar(self, trecho, timeout=15):

        # Calcula o prazo com relógio monotônico, que não depende de ajustes do relógio civil.
        fim = time.monotonic() + timeout

        # Protege a consulta ao histórico contra a thread que acrescenta linhas.
        with self.condicao:

            # Repete a busca enquanto o prazo ainda não tiver acabado.
            while time.monotonic() < fim:

                # Examina as linhas já registradas do processo.
                for linha in self.linhas:

                    # Confere se a linha contém a evidência procurada.
                    if trecho in linha:

                        # Devolve a linha encontrada para o cenário chamador.
                        return linha

                # poll retorna None se o filho está ativo; outro valor indica que terminou.
                if self.processo.poll() is not None:

                    # Se terminou sem produzir a evidência, não precisa esperar o prazo restante.
                    break

                # Libera o lock e espera notificação ou até 0.2 segundo, respeitando o prazo.
                # Ao voltar, readquire o lock e reavalia a condição.
                self.condicao.wait(min(0.2, max(0, fim - time.monotonic())))

        # Falha com o histórico completo para ajudar a entender o problema.
        raise AssertionError(f"Não apareceu {trecho!r}. Saída:\n" + "\n".join(self.linhas))

    # Simula a entrada que o usuário digitaria no terminal; não é envio entre serviços.
    def enviar(self, texto):

        # Escreve no stdin do programa filho, incluindo as quebras de linha fornecidas.
        self.processo.stdin.write(texto)

        # Libera o buffer para o filho receber os comandos imediatamente.
        self.processo.stdin.flush()

    # Encerra o processo e os recursos de leitura ao finalizar o cenário.
    def fechar(self):

        # Só solicita encerramento se o processo ainda estiver ativo.
        if self.processo.poll() is None:

            # Pede término ao sistema operacional; não depende de digitar no menu.
            self.processo.terminate()

            # Limita o tempo aguardado após pedir o término.
            try:

                # Espera até cinco segundos pela saída do filho.
                self.processo.wait(timeout=5)

            # Se o filho não terminar a tempo, usa encerramento forçado.
            except subprocess.TimeoutExpired:

                # Força o término conforme o mecanismo disponível na plataforma.
                self.processo.kill()

                # Espera o sistema confirmar o término após kill.
                self.processo.wait(timeout=5)

        # Dá até dois segundos para a thread leitora observar o fim do fluxo.
        self.thread.join(timeout=2)

        # Fecha o pipe de entrada mantido pelo controlador do teste.
        self.processo.stdin.close()

        # Fecha o pipe de saída mantido pelo controlador.
        self.processo.stdout.close()


# Cinco cenários executados contra RabbitMQ real.
class IntegracaoTest(unittest.TestCase):

    # Marca a preparação que roda uma vez para a classe inteira.
    @classmethod

    # Prepara os recursos compartilhados antes do primeiro teste.
    def setUpClass(cls):

        # Gera chaves ausentes e distribui as públicas; preserva privadas existentes.
        gerar_chaves()

        # [AMQP VIA COMUM] Declara a topologia e remove mensagens de sessões anteriores.
        preparar(limpar=True)

    # Roda antes de cada cenário para começar sem mensagens residuais.
    def setUp(self):

        # [AMQP VIA COMUM] Repete a limpeza das filas, exigindo ausência de consumidores.
        preparar(limpar=True)

        # Lista dos processos que este cenário criou e terá de encerrar.
        self.processos = []

    # Roda ao fim de cada teste que completou setUp, inclusive se uma asserção falhar.
    def tearDown(self):

        # Fecha na ordem inversa à criação, começando pelos últimos processos abertos.
        for processo in reversed(self.processos):

            # Encerra o filho e fecha seus pipes.
            processo.fechar()
        # Aguarda o broker observar o fechamento dos consumidores antes da próxima sessão.

        # Limita a cinco segundos a espera para o broker reconhecer desconexões.
        fim = time.monotonic() + 5

        # Tenta limpar até conseguir ou atingir o prazo.
        while True:

            # O broker pode ainda informar consumidor ativo imediatamente após fechar um filho.
            try:

                # [AMQP VIA COMUM] Verifica consumidores e tenta limpar as filas novamente.
                preparar(limpar=True)

                # Sai do laço assim que a preparação termina normalmente.
                break

            # A limpeza gera RuntimeError enquanto ainda observa consumidores ativos.
            except RuntimeError:

                # Confere se o limite de espera já terminou.
                if time.monotonic() >= fim:

                    # Propaga o erro atual se não conseguiu limpar a tempo.
                    raise

                # Espera 0.1 segundo antes de repetir, evitando consultas em laço ocupado.
                time.sleep(0.1)

    # Auxiliar que inicia um serviço e aguarda sua mensagem de prontidão.
    def iniciar(self, modulo, *args, **ambiente):

        # Instancia o encapsulamento e inicia de fato o processo filho.
        processo = Processo(modulo, *args, **ambiente)

        # Registra imediatamente o processo para posterior limpeza do cenário.
        self.processos.append(processo)

        # Para consumidores, o nome é c1/c2 do primeiro argumento; nos outros, o módulo.
        nome = args[0] if modulo == "consumidores" else modulo

        # Espera o serviço ter preparado o consumo/publicação, evitando avançar cedo demais.
        processo.esperar(f"PRONTO {nome}")

        # Retorna o objeto usado para digitar e observar o terminal.
        return processo

    # Sobe o conjunto mínimo do fluxo de pedidos com decisão de pagamento controlada.
    def fluxo(self, probabilidade):

        # Inicia o Estoque e guarda referência para conferir seus saldos impressos.
        estoque = self.iniciar("estoque")

        # Passa a probabilidade pelo ambiente, como string, antes de abrir o Pagamento.
        self.iniciar("pagamento", PROB_APROVACAO=str(probabilidade))

        # Inicia a Entrega para consumir aprovações.
        self.iniciar("entrega")

        # Inicia o Principal com menu e consumidor.
        principal = self.iniciar("principal")

        # Simula informar o nome Teste no primeiro prompt do menu.
        principal.enviar("Teste\n")

        # Espera o menu estar disponível para digitar uma operação.
        principal.esperar("1 Produtos")

        # Retorna os dois terminais usados diretamente nas verificações do cenário.
        return principal, estoque

    # Cria pedido pelo menu real e extrai seu ID impresso.
    def criar(self, principal, itens):

        # Marca o ponto atual do histórico para não capturar um ID de pedido anterior.
        inicio = len(principal.linhas)

        # Digita opção 2, Enter, itens e Enter no stdin do Principal.
        principal.enviar(f"2\n{itens}\n")

        # Define o prazo de até quinze segundos para o menu imprimir a criação.
        fim = time.monotonic() + 15

        # Procura o resultado enquanto o prazo não terminar.
        while time.monotonic() < fim:

            # Examina somente as linhas adicionadas depois de iniciar esta criação.
            for linha in principal.linhas[inicio:]:

                # Busca CRIADO seguido do ID de 36 caracteres, com captura entre parênteses.
                # A regex extrai o identificador esperado, sem validar integralmente um UUID.
                resultado = re.search(r"CRIADO ([0-9a-f-]{36})", linha)

                # Verifica se encontrou o padrão em uma linha.
                if resultado:

                    # Devolve somente o grupo do ID, sem o prefixo CRIADO.
                    return resultado.group(1)

            # Pausa cinquenta milissegundos para permitir novas saídas do processo.
            time.sleep(0.05)

        # Falha mostrando o histórico se a criação não aparecer a tempo.
        self.fail("Pedido não criado: " + "\n".join(principal.linhas))

    # Cenário de sete processos simultâneos, menu ativo, exclusão lógica e falta de saldo.
    def test_aprovacao_menu_ativo_exclusao_e_falta_de_estoque(self):

        # Probabilidade 1 garante aprovação dos pedidos que tiverem reserva.
        principal, estoque = self.fluxo(1)

        # Acrescenta o consumidor de categorias A/B.
        self.iniciar("consumidores", "c1")

        # Acrescenta C2 e guarda referência para observar uma promoção.
        c2 = self.iniciar("consumidores", "c2")

        # Inicia promoções com intervalo curto para acelerar o teste.
        self.iniciar("promocoes", INTERVALO_PROMOCOES="0.1")

        # Confirma que ao menos uma promoção já chegou ao consumidor.
        c2.esperar("PROMOCAO c2")
        # Os sete processos coexistem: promoções continuam durante o fluxo de pedidos.

        # Pede duas unidades do produto 1 enquanto todos os processos estão ativos.
        pedido_id = self.criar(principal, "1:2")
        # Nenhuma entrada adicional: o consumidor atualiza enquanto o menu espera input().

        # Espera envio sem digitar nada: demonstra consumo paralelo ao input do menu.
        principal.esperar(f"STATUS {pedido_id} enviado")

        # Depois do envio, digita a opção de consultar pedidos.
        principal.enviar("4\n")

        # Confere que a consulta exibe o mesmo pedido como enviado.
        principal.esperar(f"{pedido_id} | enviado")

        # Digita exclusão manual e o ID do pedido enviado.
        principal.enviar(f"3\n{pedido_id}\n")

        # Espera devolução das duas unidades, coerente com a exclusão lógica escolhida.
        estoque.esperar(f"DEVOLUCAO {pedido_id} {{'1': 2}} SALDOS {{'1': 10")

        # Solicita onze unidades, acima das dez disponíveis após a devolução.
        indisponivel = self.criar(principal, "1:11")

        # Confere exclusão automática por indisponibilidade.
        principal.esperar(f"STATUS {indisponivel} excluido estoque.indisponivel")

        # Confere reserva vazia na exclusão e saldo ainda igual a dez.
        estoque.esperar(f"DEVOLUCAO {indisponivel} {{}} SALDOS {{'1': 10")

    # Cenário de recusa após reserva, com devolução das quantidades.
    def test_recusa_restitui_reserva(self):

        # Probabilidade 0 garante recusa no Pagamento.
        principal, estoque = self.fluxo(0)

        # Cria pedido de dois Cadernos e uma Camiseta.
        pedido_id = self.criar(principal, "1:2,2:1")

        # Espera o Principal marcar excluído devido ao pagamento recusado.
        principal.esperar(f"STATUS {pedido_id} excluido pagamento.recusado")

        # Verifica no Estoque a devolução exata e o retorno dos dois saldos a dez.
        estoque.esperar(f"DEVOLUCAO {pedido_id} {{'1': 2, '2': 1}} SALDOS {{'1': 10, '2': 10")

    # Cenário que diferencia falha criptográfica, erro de negócio e evento repetido.
    def test_assinatura_invalida_descartada_e_repeticao_ignorada(self):

        # Inicia somente Estoque: o teste atuará como produtor controlado.
        estoque = self.iniciar("estoque")

        # [AMQP VIA COMUM] Abre publicador com as chaves do Principal.
        publicador = Publicador("principal")

        # Garante fechamento do publicador mesmo se a verificação falhar.
        try:

            # Monta pedido válido localmente; não inicia outro processo Principal neste cenário.
            tipo, dados = Principal().criar("Teste", [("1", 2)])

            # Assina uma única vez, preservando event_id para testar repetição dos mesmos bytes.
            valido = publicador.assinador.assinar(tipo, dados)

            # Decodifica o corpo para adulterar um campo.
            adulterado = json.loads(valido)

            # Muda o cliente sem recalcular a assinatura.
            adulterado["data"]["cliente"] = "Adulterado"

            # [AMQP VIA COMUM: ENVIO] Publica os bytes adulterados diretamente.
            # Reassinar aqui eliminaria a adulteração que este caso pretende detectar.
            publicar_corpo(publicador.canal, tipo, serializar(adulterado))

            # Espera a mensageria do Estoque registrar rejeição da assinatura.
            estoque.esperar("DESCARTADO pedido.criado")
            # Mesmo assinado por um produtor conhecido, conteúdo inválido é descartado.

            # Obtém outra cópia dos dados válidos para testar a validação de negócio.
            malformado = json.loads(valido)["data"]

            # Troca o ID string de um produto por uma lista inválida.
            malformado["itens"][0]["produto_id"] = []

            # [AMQP VIA COMUM: ENVIO] Gera assinatura válida para conteúdo malformado.
            # A rejeição esperada vem do contrato de pedido, não da assinatura.
            publicador.publicar(tipo, malformado)

            # [AMQP VIA COMUM: ENVIO] Entrega a mensagem originalmente válida.
            publicar_corpo(publicador.canal, tipo, valido)

            # [AMQP VIA COMUM: ENVIO] Repete os mesmos bytes e o mesmo event_id.
            publicar_corpo(publicador.canal, tipo, valido)

            # Confirma que a mensagem válida realizou uma reserva.
            estoque.esperar(f"RESERVA {dados['pedido_id']}")

            # [AMQP VIA COMUM: ENVIO] Publica a exclusão após as duas entregas válidas.
            publicador.publicar("pedido.excluido", {"pedido_id": dados["pedido_id"]})

            # Espera a devolução; as mensagens deste publicador chegam à mesma fila na ordem
            # dos envios, permitindo observar os resultados anteriores antes das contagens.
            estoque.esperar(f"DEVOLUCAO {dados['pedido_id']} {{'1': 2}} SALDOS {{'1': 10")

            # Conta os registros de reserva: a repetição não pode gerar uma segunda reserva.
            self.assertEqual(sum(f"RESERVA {dados['pedido_id']}" in l for l in estoque.linhas), 1)

            # Espera dois descartes: assinatura adulterada e dados de produto malformados.
            self.assertEqual(sum("DESCARTADO pedido.criado" in l for l in estoque.linhas), 2)

        # Libera o publicador mesmo se qualquer assert/espera tiver falhado.
        finally:

            # [AMQP VIA COMUM] Fecha a conexão usada para os envios do teste.
            publicador.fechar()

    # Verifica que mensagem com ID inválido não derruba o consumidor do Principal.
    def test_principal_descarta_id_invalido_e_continua_consumindo(self):

        # Inicia apenas o Principal para isolar seu tratamento de entrada.
        principal = self.iniciar("principal")

        # Informa o nome do cliente ao menu.
        principal.enviar("Teste\n")

        # Espera a interface estar pronta.
        principal.esperar("1 Produtos")

        # [AMQP VIA COMUM] Publicador controlado assume a identidade de Entrega no teste.
        publicador = Publicador("entrega")

        # Protege o fechamento da conexão temporária.
        try:

            # [AMQP VIA COMUM: ENVIO] Assina e publica envio com pedido_id de tipo inválido.
            publicador.publicar("pedido.enviado", {"pedido_id": []})

            # Espera a rejeição da mensagem no Principal.
            principal.esperar("DESCARTADO pedido.enviado")

            # Cria um pedido normal pelo menu, sem iniciar os outros estágios do fluxo.
            pedido_id = self.criar(principal, "1:1")

            # [AMQP VIA COMUM: ENVIO] Injeta confirmação válida para o novo pedido.
            # Este cenário isola a continuidade do consumo; não simula uma entrega física.
            publicador.publicar("pedido.enviado", {"pedido_id": pedido_id, "nota_id": "teste"})

            # Confirma que o consumidor continuou ativo após rejeitar a mensagem anterior.
            principal.esperar(f"STATUS {pedido_id} enviado")

        # Executa a limpeza do publicador ao sair do bloco.
        finally:

            # [AMQP VIA COMUM] Encerra a conexão temporária.
            publicador.fechar()

    # Verifica o produtor periódico e as bindings de categorias de C1/C2.
    def test_promocoes_aleatorias_e_bindings_c1_c2(self):

        # Inicia C1, inscrito em A/B.
        c1 = self.iniciar("consumidores", "c1")

        # Inicia C2, inscrito no padrão promocao.categoria.*.
        c2 = self.iniciar("consumidores", "c2")

        # Inicia o produtor aleatório com intervalo menor para o teste.
        promocoes = self.iniciar("promocoes", INTERVALO_PROMOCOES="0.1")

        # Confirma que Promoções está publicando de fato.
        promocoes.esperar("PUBLICADO promocao.categoria.")

        # Confirma que C2 recebe as publicações periódicas.
        c2.esperar("PROMOCAO c2")

        # [AMQP VIA COMUM] Abre um segundo publicador para enviar categorias controladas.
        publicador = Publicador("promocoes")

        # Garante liberação da conexão controlada ao fim das verificações.
        try:

            # Exercita separadamente cada categoria existente no catálogo.
            for categoria in "ABC":

                # UUID distingue esta publicação das promoções aleatórias simultâneas.
                marcador = str(uuid4())

                # Constrói a routing key exata da categoria atual.
                tipo = f"promocao.categoria.{categoria}"

                # [AMQP VIA COMUM: ENVIO] Publica a categoria com marcador identificável.
                publicador.publicar(tipo, {"teste": marcador, "categoria": categoria})

                # C2 deve observar o marcador de todas as três categorias.
                c2.esperar(marcador)

                # Para A e B, também se espera entrega a C1.
                if categoria in "AB":

                    # Confirma a presença do mesmo marcador no histórico de C1.
                    c1.esperar(marcador)

                # Para C, será necessário verificar ausência em C1 após uma barreira.
                else:
                    # A mensagem A posterior funciona como barreira na fila de C1.

                    # Cria marcador distinto para a próxima mensagem, de categoria A.
                    barreira = str(uuid4())

                    # [AMQP VIA COMUM: ENVIO] Envia A pelo mesmo canal após a mensagem C.
                    # Se C estivesse indevidamente roteada a C1, antecederia esta A na fila.
                    publicador.publicar("promocao.categoria.A", {"teste": barreira})

                    # Espera C1 observar a barreira antes de conferir a ausência do marcador C.
                    c1.esperar(barreira)

                    # Verifica que nenhuma linha recebida por C1 contém o marcador da categoria C.
                    self.assertFalse(any(marcador in l for l in c1.linhas))

        # Garante fechamento mesmo em falha do teste de roteamento.
        finally:

            # [AMQP VIA COMUM] Fecha a conexão do publicador controlado.
            publicador.fechar()


# Ponto de entrada: python -m scripts.teste_integracao.
if __name__ == "__main__":

    # Executa os cinco cenários com relatório detalhado, incluindo o nome de cada teste.
    unittest.main(verbosity=2)
