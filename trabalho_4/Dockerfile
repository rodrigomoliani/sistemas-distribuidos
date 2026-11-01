FROM python:3.12-slim

WORKDIR /app

# Dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Código-fonte e protos
COPY protos protos
COPY scripts scripts
COPY comum comum
COPY no no

# Compilação dos stubs gRPC
RUN python scripts/compilar_proto.py

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

CMD ["python", "-m", "no"]
