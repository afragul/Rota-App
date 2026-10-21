FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /srv

# Bağımlılıklar kaynak koddan önce kopyalanır ki katman önbelleğe alınsın.
COPY pyproject.toml README.md ./
COPY app ./app
# Migration'lar imajda; açılışta docker-entrypoint.sh uygular (RUN_MIGRATIONS=false ile kapatılır).
COPY alembic.ini docker-entrypoint.sh ./
COPY migrations ./migrations
RUN pip install --no-cache-dir .

# Root olmayan kullanıcı
RUN useradd --system --no-create-home rota
USER rota

EXPOSE 8000
ENTRYPOINT ["/srv/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
