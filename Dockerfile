FROM python:3.11-slim
WORKDIR /app/knowledge-gateway
COPY pyproject.toml ./
RUN python -c 'import tomllib, subprocess, sys; p=tomllib.load(open("pyproject.toml", "rb"))["project"]; subprocess.run([sys.executable,"-m","pip","install","--no-cache-dir",*p["dependencies"]],check=True)'
COPY README.md LICENSE ./
COPY knowledge_gateway ./knowledge_gateway
RUN pip install --no-cache-dir --no-deps .
ENTRYPOINT ["python", "-m", "uvicorn"]
CMD ["knowledge_gateway.app:app", "--host", "0.0.0.0", "--port", "8080", "--no-access-log"]
