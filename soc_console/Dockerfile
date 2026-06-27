FROM python:3.12-slim
WORKDIR /srv
COPY pyproject.toml ./
RUN pip install fastapi "uvicorn[standard]" jinja2
COPY soc_console/ ./soc_console/
CMD ["uvicorn", "soc_console.app:app", "--host", "0.0.0.0", "--port", "8000"]
