#!/bin/sh
# Konteyner açılışında önce veritabanı migration'larını uygular, sonra asıl komutu çalıştırır.
# Migration başarısız olursa konteyner HATAYLA çıkar: yanlış/eksik şemayla istek karşılamak
# (ve ilk istekte patlamak) yerine açılışta net biçimde durur.
#
# Tek `api` konteyneri varsayımıyla yazıldı. Birden çok kopya aynı anda açılacaksa
# migration'ı ayrı bir adım olarak (örn. `docker compose run --rm api alembic upgrade head`)
# çalıştırıp kopyalarda RUN_MIGRATIONS=false yap: iki kopya aynı anda migration çalıştırmamalı.
set -e

if [ "${RUN_MIGRATIONS:-true}" = "true" ]; then
    echo "Migration'lar uygulanıyor..."
    alembic upgrade head
fi

exec "$@"
