FROM python:3.11-slim

WORKDIR /srv

# CPU-only torch wheel first, to avoid pulling CUDA deps for sentence-transformers.
RUN pip install --no-cache-dir torch==2.5.1 --index-url https://download.pytorch.org/whl/cpu

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY app ./app
COPY scripts ./scripts
COPY evals ./evals

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
