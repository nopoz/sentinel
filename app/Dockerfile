FROM node:20-bookworm-slim
RUN apt-get update && apt-get install -y python3 python3-pip python3-venv && rm -rf /var/lib/apt/lists/*
WORKDIR /srv
COPY pyproject.toml ./
RUN python3 -m pip install --break-system-packages -e ".[dev]"
COPY app/ ./app/
COPY policy.yaml ./policy.yaml
ENV PYTHONUNBUFFERED=1
CMD ["python3", "-m", "uvicorn", "app.web.main:app", "--host", "0.0.0.0", "--port", "9000"]
