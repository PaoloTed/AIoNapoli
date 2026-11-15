#!/usr/bin/env bash
set -euo pipefail

# Controlled OSM import into a dedicated PostGIS schema.
#
# The PBF is imported by osm2pgsql flex into a fresh staging schema. The
# published tables have stable OIDs and are updated by osm_key in one
# transaction; rows no longer present are kept with is_current = FALSE. No
# schema rename is used, so future foreign keys remain attached to the
# published tables.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCHEMA_SQL="${OSM_SCHEMA_SQL:-$SCRIPT_DIR/osm-territory.sql}"
STYLE_FILE="${OSM_STYLE:-$SCRIPT_DIR/osm-territory.lua}"
SYNC_REFS_SQL="${OSM_SYNC_REFS_SQL:-$SCRIPT_DIR/sync-osm-refs.sql}"
if [[ ! -f "$SCHEMA_SQL" && -f /usr/local/share/osm-territory.sql ]]; then
    SCHEMA_SQL=/usr/local/share/osm-territory.sql
fi
if [[ ! -f "$STYLE_FILE" && -f /usr/local/share/osm-territory.lua ]]; then
    STYLE_FILE=/usr/local/share/osm-territory.lua
fi
if [[ ! -f "$SYNC_REFS_SQL" && -f /usr/local/share/sync-osm-refs.sql ]]; then
    SYNC_REFS_SQL=/usr/local/share/sync-osm-refs.sql
fi

PSQL_BIN="${PSQL:-psql}"
OSMIUM_BIN="${OSMIUM:-osmium}"
OSM2PGSQL_BIN="${OSM2PGSQL:-osm2pgsql}"
OSM2PGSQL_VERSION="${OSM2PGSQL_VERSION:-1.11.0}"

OSM_PBF="${OSM_PBF:-}"
DATASET_KEY="${OSM_DATASET_KEY:-osm_napoli}"
TARGET_SCHEMA="${OSM_SCHEMA:-osm_territory}"
STAGING_SCHEMA="${OSM_STAGING_SCHEMA:-${TARGET_SCHEMA}_stage_$(date -u +%Y%m%d%H%M%S)}"
SOURCE_URL="${OSM_SOURCE_URL:-}"
OSM_SNAPSHOT="${OSM_SNAPSHOT:-}"
OSM_TIMESTAMP="${OSM_TIMESTAMP:-}"
OSM_DATA_TIMESTAMP="${OSM_DATA_TIMESTAMP:-}"
ATTRIBUTION="${OSM_ATTRIBUTION:-OpenStreetMap contributors, ODbL 1.0}"
EXPECTED_SHA256="${OSM_EXPECTED_SHA256:-}"
PUBLISH="${OSM_PUBLISH:-false}"
KEEP_STAGING="${OSM_KEEP_STAGING:-false}"
STARTED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

usage() {
    cat <<'EOF'
Uso: import-osm.sh --pbf FILE [opzioni]

Opzioni:
  --pbf FILE              estratto OSM PBF
  --dataset-key KEY       chiave logica (default: osm_napoli)
  --schema NAME           schema pubblicato (default: osm_territory)
  --staging-schema NAME   staging (default: <schema>_stage_<UTC>)
  --source-url URL        provenienza (default: file://...)
  --snapshot NAME         nome dello snapshot Geofabrik (es. sud-261113)
  --osm-timestamp ISO     Last-Modified HTTP / timestamp dello snapshot
  --data-timestamp ISO    timestamp effettivo massimo degli oggetti OSM
  --expected-sha256 HEX   verifica hash del PBF
  --publish               pubblica atomicamente
  --no-publish            lascia lo staging
  --keep-staging          conserva lo schema di staging dopo la pubblicazione
  -h, --help              mostra questo aiuto

Variabili: PSQL, OSMIUM, OSM2PGSQL, OSM2PGSQL_VERSION.
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --pbf) OSM_PBF="${2:-}"; shift 2 ;;
        --dataset-key) DATASET_KEY="${2:-}"; shift 2 ;;
        --schema) TARGET_SCHEMA="${2:-}"; shift 2 ;;
        --staging-schema) STAGING_SCHEMA="${2:-}"; shift 2 ;;
        --source-url) SOURCE_URL="${2:-}"; shift 2 ;;
        --snapshot) OSM_SNAPSHOT="${2:-}"; shift 2 ;;
        --osm-timestamp) OSM_TIMESTAMP="${2:-}"; shift 2 ;;
        --data-timestamp) OSM_DATA_TIMESTAMP="${2:-}"; shift 2 ;;
        --expected-sha256) EXPECTED_SHA256="${2:-}"; shift 2 ;;
        --publish) PUBLISH=true; shift ;;
        --no-publish) PUBLISH=false; shift ;;
        --keep-staging) KEEP_STAGING=true; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Opzione sconosciuta: $1" >&2; usage >&2; exit 2 ;;
    esac
done

die() {
    echo "[osm-import ERROR] $*" >&2
    if [[ -n "${IMPORT_ID:-}" ]]; then
        "$PSQL_BIN" -X -q -v ON_ERROR_STOP=0 -v import_id="$IMPORT_ID" \
            -c "UPDATE osm_imports SET status = 'failed', finished_at = NOW(), detail = 'import fallito' WHERE import_id = $IMPORT_ID" \
            >/dev/null 2>&1 || true
    fi
    exit 1
}

[[ -n "$OSM_PBF" ]] || die "--pbf è obbligatorio"
[[ -r "$OSM_PBF" ]] || die "PBF non leggibile: $OSM_PBF"
[[ "$DATASET_KEY" =~ ^[a-z0-9_]+$ ]] || die "dataset-key non valido: $DATASET_KEY"
for schema in "$TARGET_SCHEMA" "$STAGING_SCHEMA"; do
    [[ "$schema" =~ ^[a-z_][a-z0-9_]*$ ]] || die "nome schema non valido: $schema"
done
[[ "$TARGET_SCHEMA" != "$STAGING_SCHEMA" ]] || die "target e staging coincidono"
[[ -f "$SCHEMA_SQL" ]] || die "DDL territorio non trovato: $SCHEMA_SQL"
[[ -f "$STYLE_FILE" ]] || die "stile osm2pgsql non trovato: $STYLE_FILE"

command -v "$OSM2PGSQL_BIN" >/dev/null 2>&1 || die "osm2pgsql non trovato: $OSM2PGSQL_BIN"
command -v "$PSQL_BIN" >/dev/null 2>&1 || die "psql non trovato: $PSQL_BIN"
command -v "$OSMIUM_BIN" >/dev/null 2>&1 || die "osmium non trovato: $OSMIUM_BIN"

TOOL_VERSION="$("$OSM2PGSQL_BIN" --version 2>&1 | head -1)"
[[ "$TOOL_VERSION" == *"$OSM2PGSQL_VERSION"* ]] || die \
    "versione osm2pgsql inattesa: '$TOOL_VERSION', richiesta $OSM2PGSQL_VERSION"

OSMIUM_INFO="$("$OSMIUM_BIN" fileinfo -e "$OSM_PBF" 2>/dev/null)" || die "PBF non valido: $OSM_PBF"
if [[ -z "$OSM_DATA_TIMESTAMP" ]]; then
    OSM_DATA_TIMESTAMP="$(printf '%s\n' "$OSMIUM_INFO" | awk '/^[[:space:]]*Last:/ {print $2; exit}')"
fi
SOURCE_SHA256="$(sha256sum "$OSM_PBF" | awk '{print $1}')"
if [[ -n "$EXPECTED_SHA256" && "$SOURCE_SHA256" != "$EXPECTED_SHA256" ]]; then
    die "SHA-256 PBF inatteso: $SOURCE_SHA256"
fi
DATASET_VERSION="osm-${OSM_SNAPSHOT:-snapshot}-${SOURCE_SHA256:0:16}"
SOURCE_URL="${SOURCE_URL:-file://$(readlink -f "$OSM_PBF")}"

psql_exec() {
    "$PSQL_BIN" -X -v ON_ERROR_STOP=1 "$@"
}

psql_value() {
    "$PSQL_BIN" -X -q -t -A "$@"
}

# Bootstrap the dedicated schema and metadata if migrations have not run yet.
if [[ "$(psql_value -c "SELECT to_regclass('osm_territory.osm_ways') IS NOT NULL")" != "t" ]]; then
    psql_exec -f "$SCHEMA_SQL" >/dev/null
fi

if psql_value -c "SELECT 1 FROM pg_namespace WHERE nspname = '$STAGING_SCHEMA'" | grep -q 1; then
    die "lo schema di staging esiste già: $STAGING_SCHEMA"
fi

IMPORT_ID="$(psql_exec -q -t -A \
    -v dataset_key="$DATASET_KEY" \
    -v source_url="$SOURCE_URL" \
    -v source_sha256="$SOURCE_SHA256" \
    -v dataset_version="$DATASET_VERSION" \
    -v staging_schema="$STAGING_SCHEMA" \
    -v target_schema="$TARGET_SCHEMA" \
    -v importer_version="$OSM2PGSQL_VERSION" \
    -v started_at="$STARTED_AT" <<'SQL'
INSERT INTO osm_imports (
    dataset_key, source_url, source_sha256, dataset_version,
    staging_schema, target_schema, importer_name, importer_version,
    started_at, status, detail
)
VALUES (
    :'dataset_key', NULLIF(:'source_url', ''), :'source_sha256',
    :'dataset_version', :'staging_schema', :'target_schema',
    'osm2pgsql', :'importer_version', :'started_at'::timestamptz,
    'staging', 'import in corso'
)
RETURNING import_id;
SQL
)"
[[ -n "$IMPORT_ID" ]] || die "impossibile registrare la run di import"

on_error() {
    local status=$?
    trap - ERR
    die "import fallito (run $IMPORT_ID, staging $STAGING_SCHEMA)"
}
trap on_error ERR

psql_exec -c "CREATE SCHEMA \"$STAGING_SCHEMA\";" >/dev/null

echo "[osm-import] $TOOL_VERSION -> schema staging $STAGING_SCHEMA"
"$OSM2PGSQL_BIN" \
    --create \
    --output=flex \
    --style="$STYLE_FILE" \
    --schema="$STAGING_SCHEMA" \
    --database="$PGDATABASE" \
    --user="$PGUSER" \
    --host="$PGHOST" \
    --port="$PGPORT" \
    --extra-attributes \
    --cache=2000 \
    --number-processes=4 \
    --log-level=warn \
    "$OSM_PBF" >/dev/null

WAYS="$(psql_value -c "SELECT count(*) FROM \"$STAGING_SCHEMA\".osm_ways")"
POI_NODES="$(psql_value -c "SELECT count(*) FROM \"$STAGING_SCHEMA\".poi_nodes")"
POI_WAYS="$(psql_value -c "SELECT count(*) FROM \"$STAGING_SCHEMA\".poi_way_areas")"
POI_RELATIONS="$(psql_value -c "SELECT count(*) FROM \"$STAGING_SCHEMA\".poi_relation_areas")"
POIS_TOTAL=$((POI_NODES + POI_WAYS + POI_RELATIONS))

[[ "$WAYS" -gt 0 ]] || die "nessuna way importata"
[[ "$POIS_TOTAL" -gt 0 ]] || die "nessun POI importato"

BAD_WAYS="$(psql_value -c "SELECT count(*) FROM \"$STAGING_SCHEMA\".osm_ways WHERE ST_SRID(geom) <> 4326 OR ST_GeometryType(geom) <> 'ST_LineString' OR NOT ST_IsValid(geom)")"
BAD_POIS="$(psql_value -c "
    SELECT count(*) FROM (
        SELECT geom FROM \"$STAGING_SCHEMA\".poi_nodes
        UNION ALL SELECT geom FROM \"$STAGING_SCHEMA\".poi_way_areas
        UNION ALL SELECT geom FROM \"$STAGING_SCHEMA\".poi_relation_areas
    ) p
    WHERE ST_SRID(geom) <> 4326
       OR ST_GeometryType(geom) NOT IN ('ST_Point', 'ST_Polygon', 'ST_MultiPolygon')
       OR NOT ST_IsValid(geom)
")"
[[ "$BAD_WAYS" == "0" ]] || die "geometrie way non valide/SRID errato: $BAD_WAYS"
[[ "$BAD_POIS" == "0" ]] || die "geometrie POI non valide/SRID errato: $BAD_POIS"

COUNTS_JSON="$(psql_value -c "
    SELECT json_build_object(
        'ways', (SELECT count(*) FROM \"$STAGING_SCHEMA\".osm_ways),
        'poi_nodes', (SELECT count(*) FROM \"$STAGING_SCHEMA\".poi_nodes),
        'poi_way_areas', (SELECT count(*) FROM \"$STAGING_SCHEMA\".poi_way_areas),
        'poi_relation_areas', (SELECT count(*) FROM \"$STAGING_SCHEMA\".poi_relation_areas),
        'pois_total', (SELECT count(*) FROM (
            SELECT 1 FROM \"$STAGING_SCHEMA\".poi_nodes
            UNION ALL SELECT 1 FROM \"$STAGING_SCHEMA\".poi_way_areas
            UNION ALL SELECT 1 FROM \"$STAGING_SCHEMA\".poi_relation_areas
        ) p)
    )::text
")"

psql_exec -q -t -A \
    -v import_id="$IMPORT_ID" \
    -v row_counts="$COUNTS_JSON" <<'SQL' >/dev/null
UPDATE osm_imports
SET status = 'validated', row_counts = :'row_counts'::jsonb
WHERE import_id = :import_id;
SQL

echo "[osm-import] validazione completata: $COUNTS_JSON"

if [[ "$PUBLISH" != "true" ]]; then
    trap - ERR
    echo "[osm-import] staging pronto ma NON pubblicato: $STAGING_SCHEMA (run $IMPORT_ID)"
    exit 0
fi

echo "[osm-import] pubblicazione in $TARGET_SCHEMA"
psql_exec -q \
    -v target="$TARGET_SCHEMA" \
    -v staging="$STAGING_SCHEMA" \
    -v dataset_key="$DATASET_KEY" \
    -v source_url="$SOURCE_URL" \
    -v source_sha256="$SOURCE_SHA256" \
    -v dataset_version="$DATASET_VERSION" \
    -v osm_snapshot="$OSM_SNAPSHOT" \
    -v osm_timestamp="$OSM_TIMESTAMP" \
    -v data_timestamp="$OSM_DATA_TIMESTAMP" \
    -v attribution="$ATTRIBUTION" \
    -v importer_version="$OSM2PGSQL_VERSION" \
    -v imported_at="$STARTED_AT" \
    -v row_counts="$COUNTS_JSON" \
    -v import_id="$IMPORT_ID" <<'SQL'
BEGIN;
SELECT pg_advisory_xact_lock(hashtext('osm_publish:' || :'dataset_key'));

UPDATE osm_territory.osm_ways SET is_current = FALSE WHERE is_current;
INSERT INTO osm_territory.osm_ways (
    osm_key, osm_type, osm_id, name, name_it, ref, highway, access, foot,
    bicycle, motor_vehicle, vehicle, oneway, junction, bridge, tunnel, layer,
    surface, service, maxspeed, lanes, width, tracktype, smoothness, wheelchair,
    incline, sidewalk, cycleway, footway, segregated, construction, route, tags,
    geom, source_id, dataset_version, osm_version, osm_timestamp, ingested_at,
    is_current, first_seen_at, last_seen_at
)
SELECT
    'way/' || osm_id, 'way', osm_id, name, name_it, ref, highway, access, foot,
    bicycle, motor_vehicle, vehicle, oneway, junction, bridge, tunnel, layer,
    surface, service, maxspeed, lanes, width, tracktype, smoothness, wheelchair,
    incline, sidewalk, cycleway, footway, segregated, construction, route, tags,
    geom, 'openstreetmap', :'dataset_version', osm_version,
    CASE WHEN osm_timestamp IS NULL THEN NULL ELSE to_timestamp(osm_timestamp) END,
    :'imported_at'::timestamptz, TRUE, NOW(), NOW()
FROM :"staging".osm_ways
ON CONFLICT (osm_key) DO UPDATE SET
    name = EXCLUDED.name, name_it = EXCLUDED.name_it, ref = EXCLUDED.ref,
    highway = EXCLUDED.highway, access = EXCLUDED.access, foot = EXCLUDED.foot,
    bicycle = EXCLUDED.bicycle, motor_vehicle = EXCLUDED.motor_vehicle,
    vehicle = EXCLUDED.vehicle, oneway = EXCLUDED.oneway,
    junction = EXCLUDED.junction, bridge = EXCLUDED.bridge,
    tunnel = EXCLUDED.tunnel, layer = EXCLUDED.layer,
    surface = EXCLUDED.surface, service = EXCLUDED.service,
    maxspeed = EXCLUDED.maxspeed, lanes = EXCLUDED.lanes,
    width = EXCLUDED.width, tracktype = EXCLUDED.tracktype,
    smoothness = EXCLUDED.smoothness, wheelchair = EXCLUDED.wheelchair,
    incline = EXCLUDED.incline, sidewalk = EXCLUDED.sidewalk,
    cycleway = EXCLUDED.cycleway, footway = EXCLUDED.footway,
    segregated = EXCLUDED.segregated, construction = EXCLUDED.construction,
    route = EXCLUDED.route, tags = EXCLUDED.tags, geom = EXCLUDED.geom,
    source_id = EXCLUDED.source_id, dataset_version = EXCLUDED.dataset_version,
    osm_version = EXCLUDED.osm_version, osm_timestamp = EXCLUDED.osm_timestamp,
    ingested_at = EXCLUDED.ingested_at, is_current = TRUE, last_seen_at = NOW();

UPDATE osm_territory.pois SET is_current = FALSE WHERE is_current;
WITH staged AS (
    SELECT 'node'::text AS osm_type, osm_id, name, name_it, ref, operator, brand,
           addr_street, addr_housenumber, addr_city, phone, website,
           opening_hours, wheelchair, category, category_value, tags, geom,
           osm_version, osm_timestamp
    FROM :"staging".poi_nodes
    UNION ALL
    SELECT 'way', osm_id, name, name_it, ref, operator, brand, addr_street,
           addr_housenumber, addr_city, phone, website, opening_hours,
           wheelchair, category, category_value, tags, geom, osm_version,
           osm_timestamp
    FROM :"staging".poi_way_areas
    UNION ALL
    SELECT 'relation', osm_id, name, name_it, ref, operator, brand, addr_street,
           addr_housenumber, addr_city, phone, website, opening_hours,
           wheelchair, category, category_value, tags, geom, osm_version,
           osm_timestamp
    FROM :"staging".poi_relation_areas
)
INSERT INTO osm_territory.pois (
    osm_key, osm_type, osm_id, name, name_it, ref, operator, brand, addr_street,
    addr_housenumber, addr_city, phone, website, opening_hours, wheelchair,
    category, category_value, tags, geom, label_point, source_id,
    dataset_version, osm_version, osm_timestamp, ingested_at, is_current,
    first_seen_at, last_seen_at
)
SELECT
    osm_type || '/' || osm_id, osm_type, osm_id, name, name_it, ref, operator,
    brand, addr_street, addr_housenumber, addr_city, phone, website,
    opening_hours, wheelchair, category, category_value, tags, geom,
    CASE
        WHEN ST_GeometryType(geom) = 'ST_Point' THEN geom::geometry(Point, 4326)
        ELSE ST_PointOnSurface(geom)::geometry(Point, 4326)
    END,
    'openstreetmap', :'dataset_version', osm_version,
    CASE WHEN osm_timestamp IS NULL THEN NULL ELSE to_timestamp(osm_timestamp) END,
    :'imported_at'::timestamptz, TRUE, NOW(), NOW()
FROM staged
ON CONFLICT (osm_key) DO UPDATE SET
    name = EXCLUDED.name, name_it = EXCLUDED.name_it, ref = EXCLUDED.ref,
    operator = EXCLUDED.operator, brand = EXCLUDED.brand,
    addr_street = EXCLUDED.addr_street,
    addr_housenumber = EXCLUDED.addr_housenumber,
    addr_city = EXCLUDED.addr_city, phone = EXCLUDED.phone,
    website = EXCLUDED.website, opening_hours = EXCLUDED.opening_hours,
    wheelchair = EXCLUDED.wheelchair, category = EXCLUDED.category,
    category_value = EXCLUDED.category_value, tags = EXCLUDED.tags,
    geom = EXCLUDED.geom, label_point = EXCLUDED.label_point,
    source_id = EXCLUDED.source_id, dataset_version = EXCLUDED.dataset_version,
    osm_version = EXCLUDED.osm_version, osm_timestamp = EXCLUDED.osm_timestamp,
    ingested_at = EXCLUDED.ingested_at, is_current = TRUE, last_seen_at = NOW();

INSERT INTO osm_datasets (
    dataset_key, source_url, source_sha256, dataset_version, osm_snapshot,
    osm_timestamp, data_timestamp, attribution, importer_name, importer_version, imported_at,
    published_at, row_counts, is_active
)
VALUES (
    :'dataset_key', NULLIF(:'source_url', ''), :'source_sha256',
    :'dataset_version', NULLIF(:'osm_snapshot', ''),
    NULLIF(:'osm_timestamp', '')::timestamptz,
    NULLIF(:'data_timestamp', '')::timestamptz, :'attribution', 'osm2pgsql',
    :'importer_version', :'imported_at'::timestamptz, NOW(),
    :'row_counts'::jsonb, TRUE
)
ON CONFLICT (dataset_key) DO UPDATE SET
    source_url = EXCLUDED.source_url,
    source_sha256 = EXCLUDED.source_sha256,
    dataset_version = EXCLUDED.dataset_version,
    osm_snapshot = EXCLUDED.osm_snapshot,
    osm_timestamp = EXCLUDED.osm_timestamp,
    data_timestamp = EXCLUDED.data_timestamp,
    attribution = EXCLUDED.attribution,
    importer_name = EXCLUDED.importer_name,
    importer_version = EXCLUDED.importer_version,
    imported_at = EXCLUDED.imported_at,
    published_at = NOW(),
    row_counts = EXCLUDED.row_counts,
    is_active = TRUE;

UPDATE osm_imports
SET status = 'published', finished_at = NOW(), detail = 'pubblicato in ' || :'target'
WHERE import_id = :import_id;

ANALYZE osm_territory.osm_ways;
ANALYZE osm_territory.pois;
COMMIT;
SQL

if [[ "$(psql_value -c "SELECT to_regclass('public.reference_entities') IS NOT NULL")" == "t" ]]; then
    [[ -f "$SYNC_REFS_SQL" ]] || die "sync-osm-refs.sql non trovato: $SYNC_REFS_SQL"
    psql_exec -q \
        -v osm_schema="$TARGET_SCHEMA" \
        -v dataset_key="$DATASET_KEY" \
        -v dataset_version="$DATASET_VERSION" \
        -f "$SYNC_REFS_SQL" >/dev/null
    echo "[osm-import] reference_entities OSM sincronizzate"
fi

if [[ "$KEEP_STAGING" != "true" ]]; then
    psql_exec -c "DROP SCHEMA \"$STAGING_SCHEMA\" CASCADE;" >/dev/null
    echo "[osm-import] staging rimosso: $STAGING_SCHEMA"
fi

trap - ERR
echo "[osm-import] pubblicato: $TARGET_SCHEMA (run $IMPORT_ID, dataset $DATASET_VERSION)"
