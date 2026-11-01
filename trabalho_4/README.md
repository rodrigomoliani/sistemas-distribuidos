# Trabalho 4 — Replicação de Dados, Eleição de Líder e gRPC

Trabalho prático da disciplina de Sistemas Distribuídos — UTFPR, conforme a especificação em [`Trab3_Replicação_Dados_gRPC_modelo_Pull_2026_2.pdf`](Trab3_Replicação_Dados_gRPC_modelo_Pull_2026_2.pdf).

Implementação de um sistema distribuído de replicação de dados utilizando o **modelo Pull** (Fetch-based, estilo KRaft/Kafka), **eleição de líder** (estilo Raft), quórum e suporte a leitura eventual em qualquer nó, com comunicação via **gRPC**.

## Visão Geral da Arquitetura

- **Cluster de 4 nós ($N = 4$):** Todos os nós executam a mesma base de código e transitam dinamicamente entre os papéis de **Seguidor**, **Candidato** e **Líder**.
- **Cliente:** Envia requisições de gravação (com redirecionamento automático caso contate um seguidor/candidato) e consultas de leitura distribuída em qualquer réplica.
- **Quórum ($Q = 3$):** Exige maioria absoluta para aprovação de termos e avanço do índice de *commit*; sem quórum, novas escritas são bloqueadas/rejeitadas.
- **Modelo Pull & Heartbeat:** As réplicas buscam atualizações periodicamente via `FetchRequest`, que também funciona como sinal de atividade (*heartbeat*). O líder monitora o timeout individual de cada réplica.
- **Persistência em Disco:** Cada nó armazena localmente o termo atual, o voto concedido, o log de operações e o estado consolidado do banco de dados comitado.

