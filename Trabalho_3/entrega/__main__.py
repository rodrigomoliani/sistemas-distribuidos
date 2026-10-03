# Entrada HTTP do microsserviço: inicia sua aplicação FastAPI pelo Uvicorn.

# Importa executor dos microsserviços que não precisam de API HTTP.
from comum.servico import executar

# Importa modelo com as regras de negócio do microsserviço entrega.
from entrega.modelo import Entrega

# Executa a entrada do serviço somente quando este módulo é iniciado diretamente.
if __name__ == "__main__":

    # Executa executar para concluir esta etapa do processamento.
    executar("entrega", Entrega)
