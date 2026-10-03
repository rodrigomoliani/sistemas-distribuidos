# Usa a imagem oficial com o runtime necessário ao serviço.
FROM python:3.12-slim

# Define /app como diretório de trabalho para os módulos e arquivos copiados.
WORKDIR /app

# Copia requirements.txt para a imagem, respeitando as exclusões do .dockerignore.
COPY requirements.txt .

# Instala as dependências fixadas sem manter o cache de download na imagem.
RUN pip install --no-cache-dir -r requirements.txt

# Copia comum para a imagem, respeitando as exclusões do .dockerignore.
COPY comum comum

# Copia principal para a imagem, respeitando as exclusões do .dockerignore.
COPY principal principal

# Copia estoque para a imagem, respeitando as exclusões do .dockerignore.
COPY estoque estoque

# Copia pagamento para a imagem, respeitando as exclusões do .dockerignore.
COPY pagamento pagamento

# Copia entrega para a imagem, respeitando as exclusões do .dockerignore.
COPY entrega entrega

# Copia promocoes para a imagem, respeitando as exclusões do .dockerignore.
COPY promocoes promocoes

# Copia mock_pagamento para a imagem, respeitando as exclusões do .dockerignore.
COPY mock_pagamento mock_pagamento

# Define o processo padrão iniciado quando o contêiner executa.
CMD ["python", "-m", "principal"]
