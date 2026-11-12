# Trabalho 4 — Replicação de Dados, Eleição de Líder e gRPC

Trabalho prático da disciplina de Sistemas Distribuídos — UTFPR, conforme a especificação em [`Trab3_Replicação_Dados_gRPC_modelo_Pull_2026_2.pdf`](Trab3_Replicação_Dados_gRPC_modelo_Pull_2026_2.pdf).

Implementação de um sistema distribuído de replicação de dados utilizando o **modelo Pull** (Fetch-based, estilo KRaft/Kafka), **eleição de líder** (estilo Raft), quórum e suporte a leitura eventual em qualquer nó, com comunicação via **gRPC**.

---

## Visão Geral da Arquitetura

O ambiente é composto por **5 processos distintos**, conforme a especificação oficial:
- **1 Cliente:** Envia requisições de gravação (com redirecionamento automático caso contate um seguidor/candidato) e consultas de leitura distribuída em qualquer réplica.
- **4 Nós do Cluster ($N = 4$):** Todos os nós executam a mesma base de código e transitam dinamicamente entre os papéis de **Seguidor**, **Candidato** e **Líder**.

### Regras do Consenso
- **Quórum ($Q = 3$):** Exige maioria absoluta para aprovação de termos e avanço do índice de *commit*; sem quórum, novas escritas são bloqueadas/rejeitadas.
- **Modelo Pull & Heartbeat:** As réplicas buscam atualizações periodicamente via `FetchRequest` (a cada 100 ms), que também funciona como sinal de atividade (*heartbeat*). O líder monitora o timeout individual de cada réplica.
- **Persistência em Disco:** Cada nó armazena localmente em disco três artefatos:
  1. `metadados.json`: termo atual (`current_term`), voto concedido (`voted_for`) e índice de commit.
  2. `log.json`: lista sequencial de entradas de log (`index`, `term`, `key`, `value`).
  3. `banco_comitado.json`: estado consolidado da máquina de estados (apenas dados efetivados com $index \le commit\_index$).

---

## Como Executar

### 1. Iniciar os 5 Processos com Docker Compose

Suba os 4 nós do cluster e o cliente orquestrados em rede isolada:

```bash
docker compose up -d --build
```

Para verificar que os 5 processos estão ativos:
```bash
docker compose ps
```

---

## Uso do Cliente CLI

O cliente pode ser executado diretamente no host ou dentro do container Docker:

### No Host:
```bash
# Consultar status do cluster
python3 -m cliente status

# Gravar dados (redireciona automaticamente para o líder caso contate um seguidor)
python3 -m cliente write chave valor --node 2

# Ler dados em um nó específico
python3 -m cliente read chave --node 3

# Ler dados em todas as réplicas (comprova a consistência distribuída)
python3 -m cliente read chave --todos

# Modo interativo
python3 -m cliente
```

### No Container Docker:
```bash
docker compose exec cliente python -m cliente status
docker compose exec cliente python -m cliente write chave valor --node 3
docker compose exec cliente python -m cliente read chave --todos
```

---

## Demonstração dos Cenários da Avaliação

### Cenários 1, 2, 3 e 4A
Executa em sequência os cenários de escrita/leitura, queda do líder com eleição em novo termo, bloqueio por perda de quórum e recuperação de réplica desatualizada:

```bash
python3 -m scripts.testar_cenarios
```

### Cenário 4B — Truncamento de Log por Divergência
Demonstração passo a passo exigida no PDF:
1. Grava uma entrada no líder antes do quórum (`dado_orfao`).
2. Derruba o líder (crash) e elege um novo líder em um novo termo.
3. Grava uma nova entrada válida no novo líder (`dado_valido`).
4. Religa o antigo líder: ele se torna Seguidor, detecta a divergência via `FetchRequest`, **trunca e deleta** o `dado_orfao` em disco e sincroniza com o novo líder.

```bash
python3 -m scripts.demonstrar_cenario_4b
```

O cenário 4B interrompe o líder após verificar que a entrada foi gravada sem
commit. Caso a janela de tempo expire antes da gravação, o roteiro informa a
falha e deve ser executado novamente; ele não anuncia um truncamento não observado.

### Cenário 5 — Isolamento de entradas não comitadas

O teste abaixo usa um líder simulado por um servidor gRPC real e faz a réplica
buscar a entrada por Fetch. Ele verifica uma leitura gRPC antes e outra depois de
o líder informar o avanço do commit:

```bash
python3 -m unittest discover -s tests -p test_regressoes.py -v
```

---

## Testes Unitários e de Consenso

Para executar a suíte completa de testes unitários locais:

```bash
python3 -m unittest discover -s tests -v
```
