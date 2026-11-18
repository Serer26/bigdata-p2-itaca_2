#!/usr/bin/env bash
# Carga en PostgreSQL los volcados SQL de ITACA (una tabla por fichero, con
# todos los cursos ya unificados y la columna "anyo").
#
# Uso:  ./ingesta/cargar_sql.sh [carpeta_sql]   (por defecto data/raw/sqlBigData)
#
# Cada fichero hace DROP + CREATE de su tabla, así que se puede ejecutar varias
# veces sin duplicar datos. Todo va en una única transacción.

set -euo pipefail

PROYECTO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SQL_DIR="${1:-$PROYECTO_DIR/data/raw/sqlBigData}"
TABLAS=(alumnos calificaciones contenidos cursos grupos)
CONTENEDOR="bigdata-postgres"

set -a; source "$PROYECTO_DIR/.env"; set +a

for tabla in "${TABLAS[@]}"; do
    if [[ ! -f "$SQL_DIR/$tabla.sql" ]]; then
        echo "ERROR: falta $SQL_DIR/$tabla.sql" >&2
        exit 1
    fi
done

echo "Cargando ficheros de $SQL_DIR en $POSTGRES_DB ($CONTENEDOR)"
for tabla in "${TABLAS[@]}"; do
    cat "$SQL_DIR/$tabla.sql"
done | docker exec -i "$CONTENEDOR" \
    psql -q -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 --single-transaction

echo "Filas por tabla y curso:"
for tabla in "${TABLAS[@]}"; do
    docker exec "$CONTENEDOR" psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -At -F ' ' \
        -c "SELECT '$tabla', anyo, count(*) FROM $tabla GROUP BY anyo ORDER BY anyo;"
done
