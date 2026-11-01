# Trabalho 4 — Replicação de Dados, Eleição de Líder e gRPC

Trabalho prático da disciplina de Sistemas Distribuídos — UTFPR, conforme a especificação em [`Trab3_Replicação_Dados_gRPC_modelo_Pull_2026_2.pdf`](Trab3_Replicação_Dados_gRPC_modelo_Pull_2026_2.pdf).

Implementação de um sistema distribuído de replicação de dados utilizando o **modelo Pull** (Fetch-based, estilo KRaft/Kafka), **eleição de líder** (estilo Raft), quórum e suporte a leitura eventual em qualquer nó, com comunicação via **gRPC**.

---

## Visão Geral da Arquitetura

- **Cluster de 4 nós ($N = 4$):** Todos os nós executam a mesma base de código e transitam dinamicamente entre os papéis de **Seguidor**, **Candidato** e **Líder**.
- **Cliente:** Envia requisições de gravação (com redirecionamento automático caso contate um seguidor/candidato) e consultas de leitura distribuída em qualquer réplica.
- **Quórum ($Q = 3$):** Exige maioria absoluta para aprovação de termos e avanço do índice de *commit*; sem quórum, novas escritas são bloqueadas/rejeitadas.
- **Modelo Pull & Heartbeat:** As réplicas buscam atualizações periodicamente via `FetchRequest` (a cada 100 ms), que também funciona como sinal de atividade (*heartbeat*). O líder monitora o timeout individual de cada réplica.
- **Persistência em Disco:** Cada nó armazena localmente em disco três artefatos:
  1. `metadados.json`: termo atual (`current_term`), voto concedido (`voted_for`) e índice de commit.
  2. `log.json`: lista sequencial de entradas de log (`index`, `term`, `key`, `value`).
  3. `banco_comitado.json`: estado consolidado da máquina de estados (apenas dados efetivados com $index \le commit\_index$).

---

## Como Executar

### 1. Iniciar o Cluster com Docker Compose

Suba os 4 nós do cluster orquestrados em rede isolada:

```bash
docker compose up -d --build
```

Os 4 nós iniciarão como seguidores e dispararão eleições automáticas com *election timeout* aleatório (1.5s a 3.0s).

### 2. Verificar o Estado do Cluster

Execute o script de diagnóstico ou use o cliente:

```bash
python3 -m scripts.verificar_cluster
```

ou

```bash
python3 -m cliente.client status
```

---

## Uso do Cliente CLI

O cliente interativo permite realizar operações diretamente contra o cluster:

```bash
# Modo Interativo
python3 -m cliente.client

# Consultar status do cluster
python3 -m cliente.client status

# Gravar dados (redireciona automaticamente para o líder caso contate um seguidor)
python3 -m cliente.client write chave valor --node 1

# Ler dados em um nó específico
python3 -m cliente.client read chave --node 2

# Ler dados em todas as réplicas (comprova a consistência distribuída)
python3 -m cliente.client read chave --todos
```

---

## Cenários de Testes Obrigatórios

Para executar a demonstração automatizada de todos os cenários da professora em sequência:

```bash
python3 -m scripts.testar_cenarios
```

O script testa e valida:
1. **Cenário 1 — Escrita Normal e Leitura Distribuída**: Gravação no líder e verificação da leitura consolidada nas 4 réplicas.
2. **Cenário 2 — Eleição Automática por Queda do Líder**: Queda do líder atual via Docker, detecção de ausência e eleição automática de um novo líder em novo termo.
3. **Cenário 3 — Bloqueio por Perda de Quórum**: Queda de nós até restar menos de 3 nós ativos ($N < 3$) e comprovação de que o líder recusa/bloqueia novas escritas.
4. **Cenário 4A — Recuperação de Réplica Desatualizada**: Religamento dos nós e recuperação automática de todas as entradas faltantes via `FetchRequest`.

### Testes Unitários e de Consenso

Para executar a suíte completa de testes unitários locais:

```bash
python3 -m unittest discover -s tests -v
```
