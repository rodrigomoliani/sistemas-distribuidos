FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY comum comum
COPY principal principal
COPY estoque estoque
COPY pagamento pagamento
COPY entrega entrega
COPY promocoes promocoes
COPY mock_pagamento mock_pagamento

CMD ["python", "-m", "principal"]
