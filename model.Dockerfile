FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTENSOR_FLAGS=base_compiledir=/tmp/pytensor
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends g++ && rm -rf /var/lib/apt/lists/*
COPY model/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY model model
COPY scripts/update_model.py scripts/update_model.py
ENTRYPOINT ["python", "scripts/update_model.py", "--data-dir", "/data", "--output", "/data/model-output.json"]
