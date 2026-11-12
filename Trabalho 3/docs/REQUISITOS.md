# Correspondência com o enunciado

Fonte: `Trab2_REST_MOM_SSE_2026_2.pdf`, páginas 1 a 4. A numeração de trabalhos nos PDFs difere da organização do repositório: o Trabalho 2 implementa o e-commerce anterior e o Trabalho 3 o evolui para web.

| Exigência | Implementação | Evidência |
| --- | --- | --- |
| Frontend em linguagem diferente do backend | JavaScript + HTML/CSS; backend Python | `frontend/app.js`, módulos Python |
| Catálogo e criação de pedidos por REST | GET `/produtos`, POST `/pedidos` | `principal/api.py` |
| Checkout externo em nova aba | Link com `target="_blank"` após evento de checkout | `frontend/app.js`, `mock_pagamento/checkout.html` |
| Status por SSE | Stream `/eventos`, estoque, pagamento e envio | `principal/api.py`, `principal/modelo.py` |
| Cadastro e cancelamento de interesses | PUT e DELETE `/interesses`, categorias A/B/C e e-mail | Gateway e formulário web |
| Gateway publica ações no RabbitMQ | `pedido.criado`, `pedido.excluido`, `interesse.promocao` | Outbox do Principal |
| Gateway consome resultados de Estoque, Pagamento e Entrega | Bindings das cinco mudanças exigidas e checkout | `comum/mensageria.py` |
| Gateway consulta Estoque diretamente por REST | Cliente HTTP GET `/produtos` do Estoque | `obter_produtos` em `principal/api.py` |
| Estoque consome criação/exclusão e reserva produtos | Transação única para todos os itens; devolução idempotente | `estoque/modelo.py` |
| Estoque persiste produtos | SQLite com produtos e reservas | Banco exclusivo de Estoque |
| Estoque expõe endpoint HTTP | GET `/produtos` | `estoque/api.py` |
| Pagamento solicita cobrança e informa URL de webhook | POST REST `/cobrancas` no Mock | `pagamento/modelo.py` |
| Pagamento recebe APROVADO/RECUSADO por webhook | POST `/webhook`, validação de assinatura e cobrança | `pagamento/api.py` |
| Pagamento publica resultados | Eventos `pagamento.aprovado` e `pagamento.recusado` | Outbox do Pagamento |
| Entrega emite nota e simula despacho | Nota persistida; `pedido.enviado` | `entrega/modelo.py` |
| Promoções consome interesse | Fila com `interesse.promocao` | `promocoes/modelo.py` |
| Promoções gera ofertas para categorias e envia e-mail externo | Sorteio de descontos; chamada HTTPS a Resend | `promocoes/__main__.py`, `promocoes/email.py` |
| Mock recebe criação de cobrança via REST | POST `/cobrancas`, devolve URL | `mock_pagamento/api.py` |
| Mock oferece botões aprovado/recusado e envia webhook | Página de checkout e chamada POST HTTP ao Pagamento | Mock externo |
| Toda mensagem RabbitMQ tem assinatura assimétrica | RSA 2048, SHA-256, `Signature`, produtor/routing key verificados | `comum/seguranca.py` |
| Interface gráfica com interação apropriada | Filtros, sacola, histórico, feedback, formulários responsivos | `frontend` |

**Configuração necessária para demonstrar o requisito de API externa de e-mail:** definir `EMAIL_MODO=resend`, `RESEND_API_KEY` e remetente autorizado. `EMAIL_MODO=arquivo` permite testar sem enviar e-mails e não demonstra esse requisito sozinho.

O PDF estabelece defesa obrigatória e desenvolvimento em dupla. O roteiro técnico está em `DEFESA.md`; a identificação da dupla deve acompanhar a entrega conforme orientação da professora.
