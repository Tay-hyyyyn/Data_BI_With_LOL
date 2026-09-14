FROM python:3.12-slim
WORKDIR /workspace
COPY pyproject.toml ./
COPY apps/backend ./apps/backend
RUN pip install --no-cache-dir .
ENV DATA_BI_ROOT=/workspace/data
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--app-dir", "apps/backend", "--host", "0.0.0.0", "--port", "8000"]
