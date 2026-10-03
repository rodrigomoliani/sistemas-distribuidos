# Trabalho 3 - E-commerce com REST, RabbitMQ, SSE e webhook

Evolução do Trabalho 2 para a disciplina de Sistemas Distribuídos da UTFPR, conforme `Trab2_REST_MOM_SSE_2026_2.pdf`. Mantém Python, módulos separados por microsserviço, catálogo A/B/C, dinheiro em centavos, Pika e assinaturas RSA com o campo `Signature`. O frontend usa **JavaScript**, linguagem diferente do backend **Python**.

O sistema tem catálogo, sacola, pedidos acompanhados em tempo real, checkout externo simulado com aprovação/recusa e inscrições em promoções por e-mail. O envio real está implementado com Resend, mas exige credenciais da sua conta. O modo inicial `arquivo` registra a mensagem no SQLite e no log; esse modo serve para demonstração e **não substitui a API externa exigida na avaliação**.

## Preparação

Requisitos: Python 3.12, Node.js 20 ou superior para execução local, e Docker Desktop com contêineres Linux para o Compose. Execute no PowerShell, dentro de `Trabalho_3`:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m scripts.gerar_chaves
Copy-Item .env.example .env
```

Se não tiver o comando `py`, use o caminho do seu Python. As cinco chaves privadas RSA de 2048 bits ficam na pasta `chaves` do respectivo serviço. Cada serviço recebe cópias das chaves públicas. O gerador preserva as chaves privadas existentes; execute com serviços parados. `.env`, bancos, logs e chaves são ignorados pelo Git.

## Executar com Docker

Abra o Docker Desktop e clique em **Iniciar trabalho.cmd**, ou execute:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\iniciar.ps1
```

O script prepara as dependências/chaves e inicia RabbitMQ, os cinco microsserviços, o Mock e o frontend com Compose. Também pode executar manualmente, depois de preparar as chaves:

```powershell
docker compose up --build -d --wait
```

Abra [a loja](http://localhost:8080) e [o Swagger do Gateway](http://localhost:8000/docs). O catálogo inicia com dez unidades de Caderno (A, R$ 15,00), Camiseta (B, R$ 50,00) e Fone (C, R$ 80,00).

1. Adicione produtos à sacola e informe seu nome.
2. Clique em **Finalizar pedido**. A criação é assíncrona: HTTP 202 confirma o registro, e o Estoque verifica a reserva pelo RabbitMQ.
3. Após a confirmação do estoque e criação da cobrança, clique em **Abrir pagamento**. O checkout abre em nova aba por ação do usuário, evitando bloqueio de pop-ups.
4. Escolha **Pagamento Aprovado** ou **Pagamento Recusado**. O Mock envia um webhook HTTP ao Pagamento, que publica o resultado assinado.
5. Volte à loja. A conexão SSE atualiza a linha do tempo automaticamente. Aprovação leva à nota fiscal simulada e ao envio; recusa devolve o estoque.
6. Cadastre seu e-mail e as categorias desejadas na seção Promoções. A mesma seção permite cancelar a inscrição.

Os logs ficam em `docker compose logs -f`. Para encerrar, use `docker compose down`. Os volumes preservam os bancos e as filas para a próxima execução. Não apague volumes ou gere novas chaves com mensagens pendentes: os dados da sessão precisam continuar consistentes.

### Execução local, como no Trabalho 2

Execute Python/Node localmente e apenas o RabbitMQ no Docker:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\iniciar.ps1 -Local
```

O script usa AMQP na porta **5673** do Compose, inicia sete subprocessos e grava logs em `dados/logs`. Ctrl+C encerra esses subprocessos; `docker compose down` encerra o broker. Para usar RabbitMQ já instalado ou externo:

```powershell
$env:RABBITMQ_URL = 'amqp://guest:guest@localhost:5672/%2F'
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\iniciar.ps1 -Local -SemDocker
```

Alternativamente, execute cada comando em um terminal separado, na pasta do trabalho, usando a mesma configuração AMQP:

```powershell
.\.venv\Scripts\python.exe -u -m estoque
.\.venv\Scripts\python.exe -u -m mock_pagamento
.\.venv\Scripts\python.exe -u -m pagamento
.\.venv\Scripts\python.exe -u -m entrega
.\.venv\Scripts\python.exe -u -m promocoes
.\.venv\Scripts\python.exe -u -m principal
node .\frontend\server.mjs
```

| Serviço | Porta HTTP | Persistência local |
| --- | --- | --- |
| Gateway / Principal | 8000 | `dados/principal.sqlite3` |
| Estoque | 8001 | `dados/estoque.sqlite3` |
| Pagamento | 8002 | `dados/pagamento.sqlite3` |
| Mock externo | 8003 | `dados/mock_pagamento.sqlite3` |
| Frontend JavaScript | 8080 | Identificador e nome no navegador |
| Entrega | Sem HTTP | `dados/entrega.sqlite3` |
| Promoções | Sem HTTP | `dados/promocoes.sqlite3` |

Cada SQLite pertence exclusivamente ao seu serviço. No Compose, cada um fica em volume separado. Os serviços não leem bancos uns dos outros.

## E-mail real com Resend

No `.env`, configure:

```dotenv
EMAIL_MODO=resend
RESEND_API_KEY=re_sua_chave
EMAIL_FROM=Campus Store <ofertas@seu-dominio-verificado.com>
INTERVALO_PROMOCOES=30
```

Use remetente/domínio autorizado pela sua conta. O remetente de teste `onboarding@resend.dev` está sujeito às restrições do Resend; confira os destinatários permitidos na sua conta. Reinicie Promoções depois de alterar a configuração (`docker compose up -d --force-recreate promocoes` no Compose).

Promoções consome `interesse.promocao`, persiste e-mail/categorias e, a cada intervalo, sorteia um produto e desconto de 10%, 20% ou 30%. Envia somente aos clientes interessados naquela categoria. As ofertas são informativas e não alteram os preços dos pedidos. Um ID de envio é usado como `Idempotency-Key` na API. Falhas do provedor são registradas no log e não apagam inscrições. Uma campanha que falhou não tem garantia de reenvio posterior; o próximo ciclo gera nova oferta.

No modo `arquivo`, consulte `dados/promocoes.sqlite3`, tabela `envios`, ou o log de Promoções. Não há entrega à caixa de entrada nesse modo. Os testes automatizados usam esse modo para não enviar mensagens a terceiros.

## Arquitetura e contratos

```mermaid
flowchart TD
    F[Frontend JavaScript] -->|REST| G[Principal / Gateway Python]
    G -->|SSE| F
    G -->|GET produtos REST| E[Estoque]
    G -->|Eventos assinados| R[RabbitMQ direct]
    R --> E
    E -->|Reserva / indisponibilidade| R
    R --> P[Pagamento]
    P -->|POST cobrança REST| M[Mock externo]
    F -->|Nova aba checkout| M
    M -->|Webhook assinado HMAC| P
    P -->|Resultado / checkout| R
    R --> D[Entrega]
    D -->|Nota simulada / envio| R
    R --> G
    R --> PR[Promoções]
    PR -->|REST HTTPS| EM[API externa Resend]
```

| Serviço | Consome | Publica |
| --- | --- | --- |
| Principal | `pedido.estoque_ok`, `estoque.indisponivel`, `pagamento.checkout_criado`, `pagamento.aprovado`, `pagamento.recusado`, `pedido.enviado` | `pedido.criado`, `pedido.excluido`, `interesse.promocao` |
| Estoque | `pedido.criado`, `pedido.excluido` | `pedido.estoque_ok`, `estoque.indisponivel` |
| Pagamento | `pedido.estoque_ok`, `pedido.excluido` | `pagamento.checkout_criado`, `pagamento.aprovado`, `pagamento.recusado` |
| Entrega | `pagamento.aprovado` | `pedido.enviado` |
| Promoções | `interesse.promocao` | E-mails pela API externa |

Uma exchange `direct`, `eCommerce.trabalho3`, e cinco filas duráveis `trabalho3.<servico>` mantêm isolamento do Trabalho 2. Não há `fanout`. A exchange `topic` e os consumidores C1/C2 do trabalho anterior foram substituídos pelo cadastro de interesses e envio por e-mail exigidos neste enunciado.

O evento adicional `pagamento.checkout_criado` leva a URL do provedor ao Gateway sem consulta direta ao Pagamento. Cancelamento de interesse usa `interesse.promocao` com categorias vazias e versão incrementada. Promoções ignora versões atrasadas.

Todos os eventos AMQP usam o envelope original:

```json
{
  "event_id": "UUID",
  "producer": "principal",
  "event_type": "pedido.criado",
  "data": {"pedido_id": "UUID", "cliente": "UUID", "itens": [], "total_centavos": 1500},
  "Signature": "assinatura Base64"
}
```

O trecho é ilustrativo; pedidos reais precisam de itens válidos. Assina-se todo o envelope, exceto `Signature`, com RSA/PKCS#1 v1.5 e SHA-256. O consumidor verifica a chave pública, produtor autorizado e routing key antes de alterar dados. Assinatura garante autenticidade/integridade, e não cifra o conteúdo. Eventos inválidos são rejeitados sem reenvio.

O worker AMQP tem sua própria thread/conexão Pika. As rotas HTTP gravam eventos na outbox dentro da mesma transação dos dados, evitando compartilhar a conexão Pika entre threads. O worker publica com confirmação do broker e mensagens persistentes. A inbox registra IDs processados na mesma transação que as operações de negócio e novos eventos. Se houver interrupção entre publicação e remoção da outbox, o mesmo envelope será reenviado; o consumidor deduplica pelo `event_id`. Os modelos também protegem operações pelo `pedido_id`.

### SSE

`GET /eventos?cliente=<UUID>` usa `text/event-stream`, eventos nomeados `pedido`, IDs crescentes, heartbeat e `retry: 2000`. A linha do tempo persiste no Gateway. `EventSource` reconecta automaticamente enviando `Last-Event-ID`; o Gateway retoma após esse ID. Uma nova conexão sem ID recebe o histórico desse cliente. A interface recarrega o estado atual por REST quando recebe uma notificação SSE. Inclui confirmação/indisponibilidade de estoque, checkout, aprovação/recusa e envio. Estados atrasados não fazem um pedido enviado retroceder.

## API REST

Swagger: Gateway `/docs`, Estoque `http://localhost:8001/docs`, Pagamento `http://localhost:8002/docs` e Mock `http://localhost:8003/docs`.

| Método | Endpoint Gateway | Finalidade |
| --- | --- | --- |
| GET | `/produtos` | Consulta o MS Estoque diretamente por REST |
| POST | `/pedidos` | Registra pedido e publica `pedido.criado`; retorna 202 |
| GET | `/pedidos?cliente=UUID` | Lista pedidos do cliente |
| GET | `/pedidos/UUID?cliente=UUID` | Consulta pedido e histórico |
| DELETE | `/pedidos/UUID?cliente=UUID` | Cancela pedido ainda não pago; publica `pedido.excluido` |
| PUT | `/interesses` | Salva e-mail/categorias; publica `interesse.promocao` |
| GET | `/interesses?cliente=UUID` | Consulta inscrição |
| DELETE | `/interesses?cliente=UUID` | Solicita cancelamento de todas as categorias |
| GET | `/eventos?cliente=UUID` | Stream SSE do cliente |
| GET | `/saude` | Estado do serviço e conexão AMQP |

Exemplo para PowerShell:

```powershell
$cliente = [guid]::NewGuid().ToString()
$corpo = @{ cliente = $cliente; nome = 'Ana'; itens = @(@{produto_id='1';quantidade=2}) } | ConvertTo-Json -Depth 5
$pedido = Invoke-RestMethod 'http://localhost:8000/pedidos' -Method Post -ContentType 'application/json' -Body $corpo
Invoke-RestMethod "http://localhost:8000/pedidos/$($pedido.pedido_id)?cliente=$cliente"
```

O Gateway calcula os valores a partir da resposta REST do Estoque; o navegador não informa preços. O MS Pagamento solicita a cobrança por `POST /cobrancas` no Mock, informando `webhook_url`. O Mock deduplica pelo pedido e devolve `checkout_url`. A decisão é feita por `POST /cobrancas/{id}/decisao`. O webhook é `POST /webhook`, com `pedido_id`, `cobranca_id`, `total_centavos` e status `APROVADO`/`RECUSADO`. Headers `X-Timestamp` e `X-Signature` autenticam os bytes do corpo com HMAC-SHA256 e validade de cinco minutos. Repetir o mesmo resultado é seguro; resultado conflitante recebe 409.

## Regras e limites

- Reserva de todos os itens ou nenhum. Cancelamento e recusa devolvem a reserva registrada, uma única vez. Exclusão que chega antes da criação impede reserva tardia.
- Cancelamento manual é permitido antes de aprovação/envio. Não há estorno. Uma decisão de pagamento e um cancelamento concorrentes ainda podem disputar entre serviços; não há transação distribuída entre provedor e aplicação. Na defesa, execute os cenários separadamente.
- O cliente é um UUID gerado e salvo em `localStorage`. Filtragem de pedidos/SSE evita mistura entre clientes na interface, mas **não é autenticação**. Quem conhece o identificador pode consultar os dados da demonstração.
- Nota fiscal e transporte são simulados. Não há pagamento financeiro real.
- Uma instância por serviço e um worker Uvicorn por processo. SQLite é adequado à demonstração; não é uma implantação com réplicas escaláveis.
- Filas, inbox/outbox e bancos suportam repetições e reinícios comuns. Não há garantia de exatamente uma vez entre RabbitMQ, HTTP externo e SQLite. Não são implementados dead-letter queue, circuito de falhas, backup ou recuperação de bancos apagados.
- Se o webhook não for confirmado, o Mock preserva a decisão e permite reenviar clicando no mesmo botão. Não permite trocar o resultado. Não há reenvio automático em background.
- Configuração local usa segredo de demonstração. Configure `WEBHOOK_SECRET` igual no Mock e Pagamento. O Compose publica portas somente em `127.0.0.1`. Para acesso pela rede, ajuste URLs públicas, CORS e a publicação de portas.

## Testes e defesa

```powershell
.\.venv\Scripts\python.exe -m scripts.gerar_chaves
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node --check .\frontend\app.js
docker compose config --quiet
```

Teste de integração com **broker/vhost dedicado, filas vazias e serviços parados**:

```powershell
docker compose up -d --wait rabbitmq
$env:RABBITMQ_URL = 'amqp://trabalho3:trabalho3@localhost:5673/%2F'
.\.venv\Scripts\python.exe -m scripts.teste_integracao
```

O teste inicia os sete processos, usa bancos temporários e verifica REST, OpenAPI, aprovação/envio, recusa/devolução, falta de estoque, cancelamento, SSE real/retomada, isolamento por cliente, promoções, rejeição de adulteração e persistência após reiniciar Estoque. Não apaga filas existentes: recusa execução se houver consumidores ou mensagens pendentes. Usa e-mail em modo `arquivo`. Logs e resultado ficam em `test-results`.

Roteiro detalhado: [docs/DEFESA.md](docs/DEFESA.md). Matriz de requisitos: [docs/REQUISITOS.md](docs/REQUISITOS.md). Evidências desta execução: [docs/VALIDACAO.md](docs/VALIDACAO.md).

## Leitura do código

Os arquivos Python, JavaScript, HTML, CSS, os inicializadores e as configurações possuem comentários em português junto às linhas de código, com linhas em branco para separar cada explicação. Os comentários descrevem as rotas REST, a assinatura e o consumo de eventos, as transações SQLite, o webhook, a retomada do SSE e a interface.

O formato JSON utilizado pelo npm não aceita comentários. Por isso, `frontend/package.json` continua como manifesto executável e [frontend/package.comentado.jsonc](frontend/package.comentado.jsonc) apresenta a mesma configuração com explicações de cada linha. A cópia JSONC serve para estudo.

## Referências

- [Enunciado fornecido](https://drive.google.com/file/d/1rdkNklLDbSU9-Dz4MaGmlHJYEofs2gqp/view)
- [FastAPI: StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/)
- [Resend: envio de e-mails por API](https://resend.com/docs/api-reference/emails/send-email)
- [RabbitMQ: roteamento direct com Python](https://www.rabbitmq.com/tutorials/tutorial-four-python)
- [PyCryptodome: RSA/PKCS#1 v1.5](https://pycryptodome.readthedocs.io/en/latest/src/signature/pkcs1_v1_5.html)

O enunciado exige desenvolvimento em dupla e defesa obrigatória.
