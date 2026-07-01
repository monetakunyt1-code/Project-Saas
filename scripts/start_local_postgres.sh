#!/usr/bin/env bash

set -Eeuo pipefail

PG_BASE="$HOME/.local/share/docurapi-postgres"
PG_DATA="$PG_BASE/data"
PG_SOCKET="$PG_BASE/socket"
PG_LOG="$PG_BASE/postgres.log"
PG_PASSWORD_FILE="$PG_BASE/local_password"
PG_PORT="55432"
PG_USER="docurapi"
PG_DATABASE="docurapi"

PG_BIN="$(
    find /usr/lib/postgresql \
        -type f \
        -name initdb \
        -printf '%h\n' \
        2>/dev/null |
    sort -V |
    tail -n 1
)"

if [ -z "$PG_BIN" ] || [ ! -x "$PG_BIN/pg_ctl" ]; then
    echo "GAGAL: PostgreSQL tidak tersedia."
    exit 1
fi

if [ ! -f "$PG_DATA/PG_VERSION" ]; then
    echo "GAGAL: cluster PostgreSQL DocuRapi belum dibuat."
    exit 1
fi

if [ ! -s "$PG_PASSWORD_FILE" ]; then
    echo "GAGAL: password PostgreSQL lokal tidak tersedia."
    exit 1
fi

mkdir -p "$PG_SOCKET"

if ! "$PG_BIN/pg_ctl" \
    --pgdata="$PG_DATA" \
    status \
    >/dev/null 2>&1
then
    "$PG_BIN/pg_ctl" \
        --pgdata="$PG_DATA" \
        --log="$PG_LOG" \
        --wait \
        --timeout=60 \
        start
fi

PG_PASSWORD="$(
    tr -d '\r\n' < "$PG_PASSWORD_FILE"
)"

DATABASE_URL="postgresql://${PG_USER}:${PG_PASSWORD}@127.0.0.1:${PG_PORT}/${PG_DATABASE}"

case "${1:-}" in
    --print-env)
        printf "export DOCURAPI_DATABASE_URL='%s'\n" \
            "$DATABASE_URL"
        ;;

    --check)
        export PGPASSWORD="$PG_PASSWORD"

        "$PG_BIN/psql" \
            --host=127.0.0.1 \
            --port="$PG_PORT" \
            --username="$PG_USER" \
            --dbname="$PG_DATABASE" \
            --command="SELECT 1 AS connection_ok;"

        unset PGPASSWORD
        ;;

    *)
        echo "PostgreSQL DocuRapi aktif."
        echo "Port: $PG_PORT"
        echo ""
        echo "Pasang URL ke terminal dengan:"
        echo ""
        echo 'eval "$(bash scripts/start_local_postgres.sh --print-env)"'
        ;;
esac
