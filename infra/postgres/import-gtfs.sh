#!/usr/bin/env bash
set -euo pipefail

# Controlled GTFS import into a dedicated schema.
#
# The importer never writes GTFS tables into public. It always imports into a
# fresh staging schema, validates row counts and references, records source
# hash/version/operator, then optionally publishes by atomically renaming the
# staging schema over the previous target schema. The previous schema is kept
# with a timestamp suffix so identifiers used by future disruptions can still
# be audited; no application table is truncated.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
METADATA_SQL="${GTFS_METADATA_SQL:-$SCRIPT_DIR/gtfs-metadata.sql}"
SYNC_REFS_SQL="${GTFS_SYNC_REFS_SQL:-$SCRIPT_DIR/sync-gtfs-refs.sql}"
if [[ ! -f "$METADATA_SQL" && -f /usr/local/share/gtfs-metadata.sql ]]; then
    METADATA_SQL=/usr/local/share/gtfs-metadata.sql
fi
if [[ ! -f "$SYNC_REFS_SQL" && -f /usr/local/share/sync-gtfs-refs.sql ]]; then
    SYNC_REFS_SQL=/usr/local/share/sync-gtfs-refs.sql
fi
PSQL_BIN="${PSQL:-psql}"
GTFS_TO_SQL_BIN="${GTFS_TO_SQL:-gtfs-to-sql}"
IMPORTER_VERSION="${GTFS_VIA_POSTGRES_VERSION:-4.13.0}"

GTFS_ZIP="${GTFS_ZIP:-}"
DATASET_KEY="${GTFS_DATASET_KEY:-eav}"
TARGET_SCHEMA="${GTFS_SCHEMA:-}"
STAGING_SCHEMA="${GTFS_STAGING_SCHEMA:-}"
OPERATOR_ID="${GTFS_OPERATOR_ID:-EAV}"
OPERATOR_NAME="${GTFS_OPERATOR_NAME:-Eav srl}"
SOURCE_URL="${GTFS_SOURCE_URL:-}"
PUBLISH="${GTFS_PUBLISH:-false}"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

usage() {
    cat <<'EOF'
Uso: import-gtfs.sh --zip FILE [opzioni]

Opzioni:
  --zip FILE              archivio GTFS (.zip) da importare
  --dataset-key KEY       chiave logica del dataset (default: eav)
  --schema NAME           schema autorevole di destinazione (default: gtfs_<key>)
  --staging-schema NAME   schema di staging (default: <schema>_stage_<UTC>)
  --operator-id ID        identificativo operatore (default: EAV)
  --operator-name NAME    nome operatore (default: Eav srl)
  --source-url URL        provenienza del file (default: file://...)
  --publish               pubblica atomicamente lo staging
  --no-publish            lascia lo staging senza toccare lo schema attivo
  -h, --help              mostra questo aiuto

Variabili d'ambiente: PSQL, GTFS_TO_SQL, GTFS_VIA_POSTGRES_VERSION.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --zip) GTFS_ZIP="${2:-}"; shift 2 ;;
        --dataset-key) DATASET_KEY="${2:-}"; shift 2 ;;
        --schema) TARGET_SCHEMA="${2:-}"; shift 2 ;;
        --staging-schema) STAGING_SCHEMA="${2:-}"; shift 2 ;;
        --operator-id) OPERATOR_ID="${2:-}"; shift 2 ;;
        --operator-name) OPERATOR_NAME="${2:-}"; shift 2 ;;
        --source-url) SOURCE_URL="${2:-}"; shift 2 ;;
        --publish) PUBLISH=true; shift ;;
        --no-publish) PUBLISH=false; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Opzione sconosciuta: $1" >&2; usage >&2; exit 2 ;;
    esac
done

die() {
    echo "[gtfs-import ERROR] $*" >&2
    if [[ -n "${IMPORT_ID:-}" ]]; then
        "$PSQL_BIN" -X -q -v ON_ERROR_STOP=0 -v import_id="$IMPORT_ID" \
            -c "UPDATE gtfs_imports SET status = 'failed', finished_at = NOW(), detail = 'import fallito' WHERE import_id = $IMPORT_ID" \
            >/dev/null 2>&1 || true
    fi
    exit 1
}

[[ -n "$GTFS_ZIP" ]] || die "--zip è obbligatorio"
[[ -r "$GTFS_ZIP" ]] || die "file GTFS non leggibile: $GTFS_ZIP"
[[ "$DATASET_KEY" =~ ^[a-z0-9_]+$ ]] || die "dataset-key non valido: $DATASET_KEY"
# Derive target/staging only after CLI parsing: --dataset-key/--schema must not
# inherit a staging name computed from a previous GTFS_SCHEMA environment value.
TARGET_SCHEMA="${TARGET_SCHEMA:-gtfs_${DATASET_KEY}}"
STAGING_SCHEMA="${STAGING_SCHEMA:-${TARGET_SCHEMA}_stage_$(date -u +%Y%m%d%H%M%S)}"

for schema in "$TARGET_SCHEMA" "$STAGING_SCHEMA"; do
    [[ "$schema" =~ ^[a-z_][a-z0-9_]*$ ]] || die "nome schema non valido: $schema"
done
[[ "$TARGET_SCHEMA" != "$STAGING_SCHEMA" ]] || die "target e staging coincidono"

command -v "$GTFS_TO_SQL_BIN" >/dev/null 2>&1 || die "gtfs-to-sql non trovato: $GTFS_TO_SQL_BIN"
command -v "$PSQL_BIN" >/dev/null 2>&1 || die "psql non trovato: $PSQL_BIN"

TOOL_VERSION="$("$GTFS_TO_SQL_BIN" --version 2>/dev/null || true)"
[[ "$TOOL_VERSION" == *"$IMPORTER_VERSION"* ]] || die \
    "versione gtfs-via-postgres inattesa: '${TOOL_VERSION:-assente}', richiesta $IMPORTER_VERSION"

unzip -tq "$GTFS_ZIP" >/dev/null 2>&1 || die "archivio ZIP non valido: $GTFS_ZIP"
SOURCE_SHA256="$(sha256sum "$GTFS_ZIP" | awk '{print $1}')"
DATASET_VERSION="${DATASET_KEY}-${SOURCE_SHA256:0:16}"
SOURCE_URL="${SOURCE_URL:-file://$(readlink -f "$GTFS_ZIP")}"

WORKDIR="$(mktemp -d "${TMPDIR:-/tmp}/gtfs-import.XXXXXX")"
IMPORT_ID=""
cleanup() {
    rm -rf "$WORKDIR"
}
trap cleanup EXIT

GTFS_DIR="$WORKDIR/gtfs"
mkdir -p "$GTFS_DIR"
unzip -q "$GTFS_ZIP" -d "$GTFS_DIR"

for required in agency.txt routes.txt trips.txt stops.txt stop_times.txt; do
    [[ -s "$GTFS_DIR/$required" ]] || die "file GTFS mancante: $required"
done

psql_exec() {
    "$PSQL_BIN" -X -v ON_ERROR_STOP=1 "$@"
}

psql_value() {
    "$PSQL_BIN" -X -q -t -A "$@"
}

# Bootstrap only the metadata tables; never the application schema.
if [[ "$(psql_value -c "SELECT to_regclass('public.gtfs_imports') IS NOT NULL")" != "t" ]]; then
    [[ -f "$METADATA_SQL" ]] || die "gtfs-metadata.sql non trovato: $METADATA_SQL"
    psql_exec -f "$METADATA_SQL" >/dev/null
fi

if psql_value -c "SELECT 1 FROM pg_namespace WHERE nspname = '$STAGING_SCHEMA'" | grep -q 1; then
    die "lo schema di staging esiste già: $STAGING_SCHEMA"
fi

IMPORT_ID="$(psql_exec -q -t -A \
    -v dataset_key="$DATASET_KEY" \
    -v operator_id="$OPERATOR_ID" \
    -v source_url="$SOURCE_URL" \
    -v source_sha256="$SOURCE_SHA256" \
    -v dataset_version="$DATASET_VERSION" \
    -v staging_schema="$STAGING_SCHEMA" \
    -v target_schema="$TARGET_SCHEMA" \
    -v importer_version="$IMPORTER_VERSION" \
    -v started_at="$STARTED_AT" <<'SQL'
INSERT INTO gtfs_imports (
    dataset_key, operator_id, source_url, source_sha256, dataset_version,
    staging_schema, target_schema, importer_name, importer_version,
    started_at, status, detail
)
VALUES (
    :'dataset_key', :'operator_id', NULLIF(:'source_url', ''), :'source_sha256',
    :'dataset_version', :'staging_schema', :'target_schema',
    'gtfs-via-postgres', :'importer_version', :'started_at'::timestamptz,
    'staging', 'import in corso'
)
RETURNING import_id;
SQL
)"
[[ -n "$IMPORT_ID" ]] || die "impossibile registrare la run di import"

on_error() {
    local status=$?
    trap - ERR
    if [[ -n "$IMPORT_ID" ]]; then
        "$PSQL_BIN" -X -q -v ON_ERROR_STOP=0 \
            -v import_id="$IMPORT_ID" <<'SQL' >/dev/null 2>&1 || true
UPDATE gtfs_imports
SET status = 'failed', finished_at = NOW(), detail = 'import fallito; staging conservato'
WHERE import_id = :import_id;
SQL
    fi
    echo "[gtfs-import ERROR] import fallito (run $IMPORT_ID, staging $STAGING_SCHEMA)" >&2
    exit "$status"
}
trap on_error ERR

echo "[gtfs-import] $TOOL_VERSION -> schema staging $STAGING_SCHEMA"
"$GTFS_TO_SQL_BIN" \
    --schema "$STAGING_SCHEMA" \
    --require-dependencies \
    --ignore-unsupported \
    --trips-without-shape-id \
    --stops-location-index \
    --import-metadata \
    -- "$GTFS_DIR"/*.txt \
    | "$PSQL_BIN" -X -v ON_ERROR_STOP=1 -b >/dev/null

csv_rows() {
    local file="$1"
    if [[ ! -f "$file" ]]; then
        echo 0
        return
    fi
    awk 'END { print (NR > 0 ? NR - 1 : 0) }' "$file"
}

db_rows() {
    psql_value -c "SELECT count(*) FROM \"$STAGING_SCHEMA\".$1"
}

check_table() {
    local csv_name="$1"
    local table_name="$2"
    [[ -f "$GTFS_DIR/$csv_name" ]] || return 0
    local expected actual
    expected="$(csv_rows "$GTFS_DIR/$csv_name")"
    actual="$(db_rows "$table_name")"
    [[ "$expected" == "$actual" ]] || die \
        "conteggio $table_name non coerente: sorgente=$expected database=$actual"
}

check_table agency.txt agency
check_table routes.txt routes
check_table trips.txt trips
check_table stops.txt stops
check_table stop_times.txt stop_times
check_table calendar.txt calendar
check_table calendar_dates.txt calendar_dates
check_table shapes.txt shapes
check_table frequencies.txt frequencies

for check in \
    "stop_times|SELECT count(*) FROM \"$STAGING_SCHEMA\".stop_times st LEFT JOIN \"$STAGING_SCHEMA\".trips t ON t.trip_id = st.trip_id WHERE t.trip_id IS NULL" \
    "stop_times->stops|SELECT count(*) FROM \"$STAGING_SCHEMA\".stop_times st LEFT JOIN \"$STAGING_SCHEMA\".stops s ON s.stop_id = st.stop_id WHERE s.stop_id IS NULL" \
    "trips->routes|SELECT count(*) FROM \"$STAGING_SCHEMA\".trips t LEFT JOIN \"$STAGING_SCHEMA\".routes r ON r.route_id = t.route_id WHERE r.route_id IS NULL"
do
    label="${check%%|*}"
    query="${check#*|}"
    orphan_count="$(psql_value -c "$query")"
    [[ "$orphan_count" == "0" ]] || die "riferimenti orfani ($label): $orphan_count"
done

IFS='|' read -r SERVICE_START SERVICE_END < <(
    psql_value -c "SELECT COALESCE(min(date)::text, ''), COALESCE(max(date)::text, '') FROM \"$STAGING_SCHEMA\".service_days"
)
[[ -n "$SERVICE_START" && -n "$SERVICE_END" ]] || die \
    "calendario GTFS vuoto: service_days non contiene date utilizzabili"
AGENCY_IDS="$(psql_value -c "SELECT COALESCE(string_agg(agency_id, ',' ORDER BY agency_id), '') FROM \"$STAGING_SCHEMA\".agency")"
COUNTS_JSON="$(psql_value -c "
    SELECT json_build_object(
        'agency', (SELECT count(*) FROM \"$STAGING_SCHEMA\".agency),
        'routes', (SELECT count(*) FROM \"$STAGING_SCHEMA\".routes),
        'trips', (SELECT count(*) FROM \"$STAGING_SCHEMA\".trips),
        'stops', (SELECT count(*) FROM \"$STAGING_SCHEMA\".stops),
        'stop_times', (SELECT count(*) FROM \"$STAGING_SCHEMA\".stop_times),
        'calendar', (SELECT count(*) FROM \"$STAGING_SCHEMA\".calendar),
        'calendar_dates', (SELECT count(*) FROM \"$STAGING_SCHEMA\".calendar_dates),
        'shapes', (SELECT count(*) FROM \"$STAGING_SCHEMA\".shapes),
        'service_days', (SELECT count(*) FROM \"$STAGING_SCHEMA\".service_days)
    )::text
")"

psql_exec -q -t -A \
    -v import_id="$IMPORT_ID" \
    -v row_counts="$COUNTS_JSON" \
    -v service_start="$SERVICE_START" \
    -v service_end="$SERVICE_END" <<'SQL' >/dev/null
UPDATE gtfs_imports
SET status = 'validated', row_counts = :'row_counts'::jsonb,
    detail = json_build_object(
        'service_start', NULLIF(:'service_start', ''),
        'service_end', NULLIF(:'service_end', '')
    )::text
WHERE import_id = :import_id;
SQL

echo "[gtfs-import] validazione completata: $COUNTS_JSON"

if [[ "$PUBLISH" != "true" ]]; then
    trap - ERR
    echo "[gtfs-import] staging pronto ma NON pubblicato: $STAGING_SCHEMA (run $IMPORT_ID)"
    exit 0
fi

BACKUP_SCHEMA="${TARGET_SCHEMA}_prev_$(date -u +%Y%m%d%H%M%S)"
[[ ${#BACKUP_SCHEMA} -le 63 ]] || die "nome schema di backup troppo lungo: $BACKUP_SCHEMA"

echo "[gtfs-import] pubblicazione atomica $STAGING_SCHEMA -> $TARGET_SCHEMA"
psql_exec -q \
    -v target="$TARGET_SCHEMA" \
    -v staging="$STAGING_SCHEMA" \
    -v backup="$BACKUP_SCHEMA" \
    -v dataset_key="$DATASET_KEY" \
    -v operator_id="$OPERATOR_ID" \
    -v operator_name="$OPERATOR_NAME" \
    -v agency_ids="$AGENCY_IDS" \
    -v source_url="$SOURCE_URL" \
    -v source_sha256="$SOURCE_SHA256" \
    -v dataset_version="$DATASET_VERSION" \
    -v importer_version="$IMPORTER_VERSION" \
    -v imported_at="$STARTED_AT" \
    -v row_counts="$COUNTS_JSON" \
    -v service_start="$SERVICE_START" \
    -v service_end="$SERVICE_END" \
    -v import_id="$IMPORT_ID" <<'SQL'
BEGIN;
SELECT pg_advisory_xact_lock(hashtext('gtfs_publish:' || :'dataset_key'));
SELECT format('ALTER SCHEMA %I RENAME TO %I', :'target', :'backup')
WHERE EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = :'target') \gexec
ALTER SCHEMA :"staging" RENAME TO :"target";
INSERT INTO gtfs_datasets (
    dataset_key, operator_id, operator_name, agency_ids, source_url,
    source_sha256, dataset_version, gtfs_schema, service_start, service_end,
    importer_name, importer_version, imported_at, published_at, row_counts,
    is_active
)
VALUES (
    :'dataset_key', :'operator_id', :'operator_name', :'agency_ids',
    NULLIF(:'source_url', ''), :'source_sha256', :'dataset_version',
    :'target', NULLIF(:'service_start', '')::date,
    NULLIF(:'service_end', '')::date, 'gtfs-via-postgres',
    :'importer_version', :'imported_at'::timestamptz, NOW(),
    :'row_counts'::jsonb, TRUE
)
ON CONFLICT (dataset_key) DO UPDATE SET
    operator_id = EXCLUDED.operator_id,
    operator_name = EXCLUDED.operator_name,
    agency_ids = EXCLUDED.agency_ids,
    source_url = EXCLUDED.source_url,
    source_sha256 = EXCLUDED.source_sha256,
    dataset_version = EXCLUDED.dataset_version,
    gtfs_schema = EXCLUDED.gtfs_schema,
    service_start = EXCLUDED.service_start,
    service_end = EXCLUDED.service_end,
    importer_name = EXCLUDED.importer_name,
    importer_version = EXCLUDED.importer_version,
    imported_at = EXCLUDED.imported_at,
    published_at = NOW(),
    row_counts = EXCLUDED.row_counts,
    is_active = TRUE;
UPDATE gtfs_imports
SET status = 'published', finished_at = NOW(),
    detail = 'pubblicato; schema precedente (se presente) conservato come ' || :'backup'
WHERE import_id = :import_id;
COMMIT;
SQL

if [[ "$(psql_value -c "SELECT to_regclass('public.reference_entities') IS NOT NULL")" == "t" ]]; then
    [[ -f "$SYNC_REFS_SQL" ]] || die "sync-gtfs-refs.sql non trovato: $SYNC_REFS_SQL"
    psql_exec -q         -v gtfs_schema="$TARGET_SCHEMA"         -v dataset_key="$DATASET_KEY"         -v dataset_version="$DATASET_VERSION"         -f "$SYNC_REFS_SQL" >/dev/null
    echo "[gtfs-import] reference_entities GTFS sincronizzate"
fi

trap - ERR
echo "[gtfs-import] pubblicato: $TARGET_SCHEMA (run $IMPORT_ID, precedente $BACKUP_SCHEMA)"
