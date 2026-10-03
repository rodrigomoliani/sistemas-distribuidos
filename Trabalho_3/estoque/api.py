# Consulta REST do catálogo persistido, consumida diretamente pelo Gateway.

# Importa fábrica que prepara o ciclo de vida da API e do seu worker AMQP.
from comum.web import criar_app

# Importa modelo com as regras de negócio do microsserviço estoque.
from estoque.modelo import Estoque

# Prepara aplicação FastAPI para esta etapa.
app = criar_app("estoque", Estoque)

# Registra a rota HTTP, seu método e suas opções na documentação OpenAPI.
@app.get("/produtos", tags=["Estoque"])

# Devolve o catálogo do serviço de Estoque ou encaminha sua consulta REST no Gateway.
def produtos():

    # Devolve o resultado desta operação para a rota, modelo ou teste que a chamou.
    return app.state.modelo.produtos()
