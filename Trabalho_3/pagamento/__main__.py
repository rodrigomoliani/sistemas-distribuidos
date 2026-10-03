# Entrada HTTP do microsserviço: inicia sua aplicação FastAPI pelo Uvicorn.

# Importa servidor ASGI que executa a aplicação FastAPI em sua porta HTTP.
import uvicorn

# Executa a entrada do serviço somente quando este módulo é iniciado diretamente.
if __name__ == "__main__":

    # Inicia o servidor ASGI na porta do serviço; 0.0.0.0 permite o uso dentro do contêiner.
    uvicorn.run("pagamento.api:app", host="0.0.0.0", port=8002)
