# Roteiro de defesa

## Antes da apresentação

1. Prepare Python/dependências e chaves. Inicie o Compose ou os serviços locais como descrito no README.
2. Confira `http://localhost:8000/saude` e as conexões AMQP. Abra loja, Swagger e logs.
3. Configure Resend para demonstrar a integração externa, com remetente autorizado e e-mail de teste seu. O modo `arquivo` não entrega e-mails.
4. Explique que as operações financeiras, nota fiscal e transporte são simulados.

## Demonstração sugerida (8 a 12 minutos)

1. **Arquitetura:** JavaScript no frontend, Python nos cinco microsserviços, REST entre navegador/Gateway e Gateway/Estoque, RabbitMQ no fluxo interno, SSE de volta ao navegador. Mock de pagamento e Resend representam sistemas externos.
2. **Catálogo:** mostre estoque e preços. No Swagger, execute GET `/produtos`. Abra `obter_produtos` para mostrar que o Gateway consulta Estoque por HTTP.
3. **Aprovação:** adicione duas unidades de Caderno, informe um nome e crie o pedido. Mostre confirmação de estoque e abertura do checkout em nova aba. Aprove; volte à loja e mostre aprovação, nota simulada e envio sem atualizar a página.
4. **SSE:** na aba Network das ferramentas do navegador, observe `/eventos`, tipo `text/event-stream`, IDs e dados. Explique reconexão com `Last-Event-ID` e histórico persistido. Mostre separadamente REST 202 e o resultado assíncrono.
5. **Recusa:** crie um pedido de Camiseta e recuse no checkout. Mostre status e a quantidade devolvida ao Estoque. Clique novamente no mesmo resultado: não deve haver duplicação.
6. **Falta de estoque:** no Swagger envie uma quantidade maior que o saldo. A interface limita a seleção ao saldo exibido, mas a API permite demonstrar indisponibilidade assíncrona. Mostre que nenhum item é reservado parcialmente.
7. **Promoções:** cadastre seu e-mail e categorias. Acompanhe o log de Promoções, resposta do Resend e recebimento na caixa de entrada. Cancele a inscrição, aguarde o consumo do evento e mostre categorias vazias no banco de Promoções. Se o provedor não estiver configurado, diga que o registro em arquivo demonstra apenas a lógica, não o envio externo.
8. **Assinatura:** abra `comum/seguranca.py`. Explique chave privada por produtor, públicas nos consumidores, SHA-256 e campo `Signature`. Mostre o teste de adulteração e o descarte no log.
9. **Persistência:** reinicie Estoque e consulte o catálogo novamente. Os saldos permanecem no SQLite. Explique os volumes do Compose.

## Perguntas prováveis

**Por que não usar REST em todo o fluxo?** REST atende consultas e comandos do usuário. Os resultados das etapas percorrem filas e desacoplam os serviços. SSE permite ao servidor avisar o navegador sem polling contínuo.

**Por que SSE e não WebSocket?** O fluxo exigido de notificações é unidirecional, do Gateway ao navegador. Os comandos do usuário continuam por REST.

**Quando a URL de checkout existe?** Depois que Estoque confirma a reserva, Pagamento solicita a cobrança ao Mock e publica `pagamento.checkout_criado`. O Gateway repassa pelo estado/stream; o usuário abre a nova aba.

**Qual a diferença entre RSA e HMAC aqui?** RSA é assinatura assimétrica obrigatória dos eventos RabbitMQ, com uma privada por serviço. HMAC usa um segredo compartilhado para autenticar o webhook externo. Nenhum dos dois cifra dados.

**O que significa HTTP 202?** A ação foi registrada, mas o processamento pelos microsserviços continua de forma assíncrona. A decisão final aparece nos eventos e no estado do pedido.

**Como evita duplicação?** Inbox por ID do evento, proteção pelo pedido, outbox com envelope persistido e cobrança idempotente. No webhook, o mesmo status não publica de novo; um status conflitante é rejeitado. Isso não cria uma transação distribuída com garantia absoluta de exatamente uma vez.

**O que acontece se RabbitMQ cair?** Workers reconectam. Eventos já gravados na outbox aguardam publicação. O Gateway retorna 503 para novos comandos quando sabe que a conexão está indisponível. Os bancos não são apagados.

**Quais limites permanecem?** Identificador de navegador sem autenticação, uma instância por serviço, nota/transportadora simuladas, cancelamento concorrente com aprovação sem coordenação global e falhas de e-mail sem recuperação completa de campanhas antigas.

## Arquivos para explicar

- `comum/seguranca.py`: autenticidade e integridade.
- `comum/mensageria.py` e `comum/banco.py`: topologia, confirmação, inbox/outbox e transações.
- `principal/api.py`: REST e stream SSE.
- `estoque/modelo.py`: reserva atômica, devolução e persistência.
- `pagamento/modelo.py`, `pagamento/api.py` e `mock_pagamento/api.py`: cobrança e webhook.
- `promocoes/email.py`: integração HTTPS com a API externa.
- `scripts/teste_integracao.py`: validação com os processos reais.
