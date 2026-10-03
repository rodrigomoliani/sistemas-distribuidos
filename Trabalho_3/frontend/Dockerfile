# Usa a imagem oficial com o runtime necessário ao serviço.
FROM node:24-alpine

# Define /app como diretório de trabalho para os módulos e arquivos copiados.
WORKDIR /app

# Copia . para a imagem, respeitando as exclusões do .dockerignore.
COPY . .

# Documenta a porta do frontend; a publicação local é feita pelo Compose.
EXPOSE 8080

# Define o processo padrão iniciado quando o contêiner executa.
CMD ["node", "server.mjs"]
