from comum.web import criar_app
from estoque.modelo import Estoque

app = criar_app("estoque", Estoque)


@app.get("/produtos", tags=["Estoque"])
def produtos():
    """Devolve a lista de produtos persistidos no Estoque diretamente via REST."""
    return app.state.modelo.produtos()
