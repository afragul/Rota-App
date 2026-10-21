FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

# Bağımlılıklar kaynak koddan önce kopyalanır ki katman önbelleğe alınsın.
COPY pyproject.toml README.md ./
COPY app ./app
# Migration'lar imajda: `docker compose run --rm api alembic upgrade head`
COPY alembic.ini ./
COPY migrations ./migrations
RUN pip install --no-cache-dir .

# Root olmayan kullanıcı
RUN useradd --system --no-create-home rota
USER rota

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
