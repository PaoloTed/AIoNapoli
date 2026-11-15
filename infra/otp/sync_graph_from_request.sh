#!/usr/bin/env bash
# Rebuild OTP from the same validated GTFS archives recorded in PostgreSQL,
# validate the new graph on a temporary port, then switch the live service.
#
# Triggered by otp-graph-sync.path when download_monthly.sh writes a request,
# and periodically by otp-graph-sync.timer as a reconciliation safety net.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
DATA_DIR="${DATA_DIR:-$REPO_ROOT/data}"
REQUEST_DIR="${OTP_REBUILD_REQUEST_DIR:-$DATA_DIR/otp-rebuild}"
REQUEST_FILE=""
FORCE=false
RECONCILE=false
while [[ $# -gt 0 ]]; do
    case "$1" in
        --request) REQUEST_FILE="${2:-}"; shift 2 ;;
        --force) FORCE=true; shift ;;
        --reconcile) RECONCILE=true; shift ;;
        *) echo "Opzione sconosciuta: $1" >&2; exit 2 ;;
    esac
done
REQUEST_FILE="${REQUEST_FILE:-$REQUEST_DIR/request.json}"
STATE_FILE="$REQUEST_DIR/current.json"
RESULT_FILE="$REQUEST_DIR/last-result.json"
LOG_FILE="$REQUEST_DIR/sync.log"
LOCK_FILE="${OTP_SYNC_LOCK:-/tmp/otp-graph-sync.lock}"
OTP_JAR="${OTP_JAR:-/home/r0x4n/otp-1a/otp-shaded-2.10.0.jar}"
JAVA_BIN="${JAVA_BIN:-/usr/lib/jvm/java-25-openjdk-amd64/bin/java}"
GRAPH_ROOT="${OTP_GRAPH_ROOT:-/home/r0x4n/otp-graphs}"
LIVE_LINK="${OTP_LIVE_LINK:-/home/r0x4n/otp-live}"
OTP_UNIT="${OTP_UNIT:-otp-mobility.service}"
LIVE_PORT="${OTP_PORT:-8080}"
TEMP_PORT="${OTP_TEMP_PORT:-8081}"
EAV_ZIP="${OTP_EAV_ZIP:-$DATA_DIR/gtfs/eav-technical.gtfs.zip}"
ANM_LATEST_ZIP="${OTP_ANM_ZIP:-$DATA_DIR/gtfs/gtfs-latest.zip}"
ANM_SEED_ZIP="${OTP_ANM_SEED_ZIP:-$DATA_DIR/gtfs/anm-google-transit-20261103.gtfs.zip}"
OSM_PBF="${OTP_OSM_PBF:-$DATA_DIR/osm/napoli-eav-261113.osm.pbf}"
DATABASE_NAME="${POSTGRES_DB:-mobility}"
CONTAINER_NAME="${POSTGRES_CONTAINER:-napoli-postgres-mobility}"

mkdir -p "$REQUEST_DIR"
exec >>"$LOG_FILE" 2>&1
log() { printf '[%s] %s\n' "$(date --iso-8601=seconds)" "$*"; }

RESULT_STATUS="failed"
RESULT_DETAIL="esecuzione interrotta"
PROCESSING_FILE=""
TEMP_PID=""
DATASETS_JSON='{}'
REQUEST_ID=""

write_result() {
    local status="$1" detail="$2"
    jq -n \
        --arg status "$status" \
        --arg detail "$detail" \
        --arg request_id "$REQUEST_ID" \
        --arg version "${BUILD_DIR:-}" \
        --arg graph_sha "${GRAPH_SHA:-}" \
        --arg at "$(date --iso-8601=seconds)" \
        --argjson datasets "$DATASETS_JSON" \
        '{
            status: $status, detail: $detail, request_id: $request_id,
            version: $version, graph_sha256: $graph_sha,
            datasets: $datasets, at: $at
        }' > "$RESULT_FILE.tmp"
    mv -f "$RESULT_FILE.tmp" "$RESULT_FILE"
}

die() {
    RESULT_DETAIL="$*"
    log "ERROR: $*"
    exit 1
}

cleanup() {
    local status=$?
    if [[ -n "$TEMP_PID" ]]; then
        kill "$TEMP_PID" 2>/dev/null || true
        wait "$TEMP_PID" 2>/dev/null || true
    fi
    if [[ -n "$PROCESSING_FILE" && -f "$PROCESSING_FILE" ]]; then
        if [[ "$RESULT_STATUS" == "success" ]]; then
            mv -f "$PROCESSING_FILE" "$REQUEST_DIR/processed-${REQUEST_ID:-$(date -u +%Y%m%dT%H%M%SZ)}.json"
        else
            mv -f "$PROCESSING_FILE" "$REQUEST_DIR/failed-${REQUEST_ID:-$(date -u +%Y%m%dT%H%M%SZ)}.json"
        fi
    fi
    write_result "$RESULT_STATUS" "$RESULT_DETAIL" || true
    exit "$status"
}
trap cleanup EXIT

finish_success() {
    RESULT_STATUS="success"
    RESULT_DETAIL="$1"
    log "$1"
    exit 0
}

psql_query() {
    printf '%s\n' "$1" | sg docker -c \
        "docker exec -i -e PGUSER=postgres -e PGDATABASE=$DATABASE_NAME $CONTAINER_NAME psql -X -t -A -F'|'"
}

exec 9>"$LOCK_FILE"
flock 9

if [[ -f "$REQUEST_FILE" ]]; then
    REQUEST_ID="$(jq -r '.request_id // empty' "$REQUEST_FILE" 2>/dev/null || true)"
    REQUEST_ID="${REQUEST_ID:-$(date -u +%Y%m%dT%H%M%SZ)}"
    PROCESSING_FILE="$REQUEST_DIR/processing-${REQUEST_ID}.json"
    mv -f "$REQUEST_FILE" "$PROCESSING_FILE"
    REQUEST_SOURCE="$PROCESSING_FILE"
    log "richiesta $REQUEST_ID ricevuta"
else
    REQUEST_SOURCE=""
    RECONCILE=true
    log "riconciliazione senza file di richiesta"
fi

REQUEST_KEY="anm"
REQUEST_SCHEMA=""
REQUEST_SHA=""
REQUEST_ZIP=""
if [[ -n "$REQUEST_SOURCE" ]]; then
    REQUEST_KEY="$(jq -r '.dataset_key // "anm"' "$REQUEST_SOURCE")"
    REQUEST_SCHEMA="$(jq -r '.gtfs_schema // empty' "$REQUEST_SOURCE")"
    REQUEST_SHA="$(jq -r '.source_sha256 // empty' "$REQUEST_SOURCE")"
    REQUEST_ZIP="$(jq -r '.zip_path // empty' "$REQUEST_SOURCE")"
fi
[[ "$REQUEST_KEY" =~ ^[a-z0-9_]+$ ]] || die "dataset_key non valido: $REQUEST_KEY"

DB_ROWS="$(psql_query "SELECT dataset_key, gtfs_schema, source_sha256, service_start, service_end FROM public.gtfs_datasets WHERE is_active ORDER BY dataset_key;")"
[[ -n "$DB_ROWS" ]] || die "nessun dataset GTFS attivo nel database"

declare -A DB_SCHEMA=() DB_SHA=() DB_START=() DB_END=()
while IFS='|' read -r key schema sha start end; do
    [[ -n "$key" ]] || continue
    DB_SCHEMA["$key"]="$schema"
    DB_SHA["$key"]="$sha"
    DB_START["$key"]="$start"
    DB_END["$key"]="$end"
done <<< "$DB_ROWS"

[[ -n "${DB_SHA[$REQUEST_KEY]:-}" ]] || die "dataset '$REQUEST_KEY' non attivo nel database"
if [[ -n "$REQUEST_SHA" && "$REQUEST_SHA" != "${DB_SHA[$REQUEST_KEY]}" ]]; then
    die "hash richiesta ($REQUEST_SHA) diverso dal database (${DB_SHA[$REQUEST_KEY]})"
fi
if [[ -n "$REQUEST_SCHEMA" && "$REQUEST_SCHEMA" != "${DB_SCHEMA[$REQUEST_KEY]}" ]]; then
    die "schema richiesta ($REQUEST_SCHEMA) diverso dal database (${DB_SCHEMA[$REQUEST_KEY]})"
fi

DATASETS_JSON='{}'
for key in "${!DB_SHA[@]}"; do
    DATASETS_JSON="$(jq -c \
        --arg key "$key" \
        --arg sha "${DB_SHA[$key]}" \
        --arg schema "${DB_SCHEMA[$key]}" \
        '. + {($key): {source_sha256: $sha, gtfs_schema: $schema}}' <<<"$DATASETS_JSON")"
done

if [[ -f "$STATE_FILE" && "$FORCE" != "true" ]]; then
    SAME=true
    for key in "${!DB_SHA[@]}"; do
        state_sha="$(jq -r --arg key "$key" '.datasets[$key].source_sha256 // empty' "$STATE_FILE")"
        if [[ "$state_sha" != "${DB_SHA[$key]}" ]]; then
            SAME=false
            break
        fi
    done
    if [[ "$SAME" == "true" ]]; then
        finish_success "grafo OTP già sincronizzato con gli hash del database"
    fi
fi

declare -A ZIP_PATH=()
for key in "${!DB_SHA[@]}"; do
    case "$key" in
        eav) path="$EAV_ZIP" ;;
        anm)
            if [[ -r "$ANM_LATEST_ZIP" ]]; then
                path="$ANM_LATEST_ZIP"
            else
                path="$ANM_SEED_ZIP"
            fi
            ;;
        *) die "nessun file ZIP configurato per il dataset '$key'" ;;
    esac
    if [[ "$key" == "$REQUEST_KEY" && -n "$REQUEST_ZIP" ]]; then
        if [[ "$REQUEST_ZIP" == /data/* ]]; then
            path="$DATA_DIR/${REQUEST_ZIP#/data/}"
        else
            path="$REQUEST_ZIP"
        fi
    fi
    [[ -r "$path" ]] || die "file ZIP non leggibile per '$key': $path"
    actual_sha="$(sha256sum "$path" | awk '{print $1}')"
    [[ "$actual_sha" == "${DB_SHA[$key]}" ]] || die \
        "hash file '$key' ($actual_sha) diverso dal database (${DB_SHA[$key]}): $path"
    ZIP_PATH["$key"]="$path"
done
[[ -r "$OSM_PBF" ]] || die "PBF OSM non leggibile: $OSM_PBF"
[[ -r "$OTP_JAR" ]] || die "JAR OTP non leggibile: $OTP_JAR"

SERVICE_START="$(printf '%s\n' "${DB_START[@]}" | grep -v '^$' | sort | head -1 || true)"
SERVICE_END="$(printf '%s\n' "${DB_END[@]}" | grep -v '^$' | sort | tail -1 || true)"
SERVICE_START="${SERVICE_START:-2025-09-15}"
SERVICE_END="${SERVICE_END:-2030-12-31}"

ANM_TAG="${DB_SHA[anm]:-none}"
EAV_TAG="${DB_SHA[eav]:-none}"
BUILD_ID="$(date -u +%Y%m%dT%H%M%SZ)"
BUILD_DIR="$GRAPH_ROOT/graph-${ANM_TAG:0:8}-${EAV_TAG:0:8}-$BUILD_ID"
mkdir -p "$BUILD_DIR/otp-data" "$BUILD_DIR/artifacts"
for key in "${!ZIP_PATH[@]}"; do
    cp --reflink=auto "${ZIP_PATH[$key]}" "$BUILD_DIR/otp-data/${key}.gtfs.zip"
done
cp --reflink=auto "$OSM_PBF" "$BUILD_DIR/otp-data/napoli.osm.pbf"
jq -n \
    --arg start "$SERVICE_START" \
    --arg end "$SERVICE_END" \
    '{transitServiceStart: $start, transitServiceEnd: $end,
      transitModelTimeZone: "Europe/Rome",
      osmDefaults: {timeZone: "Europe/Rome"}}' > "$BUILD_DIR/otp-data/build-config.json"

log "build $BUILD_DIR (service $SERVICE_START..$SERVICE_END)"
"$JAVA_BIN" -Xms1g -Xmx4g -jar "$OTP_JAR" \
    --build --save "$BUILD_DIR/otp-data" \
    > "$BUILD_DIR/artifacts/otp-build.log" 2>&1 || die "build OTP fallita: $BUILD_DIR/artifacts/otp-build.log"
grep -q "Done building graph" "$BUILD_DIR/artifacts/otp-build.log" || die "build OTP senza conferma di completamento"
[[ -s "$BUILD_DIR/otp-data/graph.obj" ]] || die "graph.obj assente dopo la build"
GRAPH_SHA="$(sha256sum "$BUILD_DIR/otp-data/graph.obj" | awk '{print $1}')"

log "validazione temporanea sulla porta $TEMP_PORT"
"$JAVA_BIN" -Xms512m -Xmx2g -jar "$OTP_JAR" \
    --load --serve --port "$TEMP_PORT" "$BUILD_DIR/otp-data" \
    > "$BUILD_DIR/artifacts/otp-validate.log" 2>&1 &
TEMP_PID=$!
READY=false
for _ in $(seq 1 90); do
    if curl -fsS "http://127.0.0.1:$TEMP_PORT/otp/" >/dev/null 2>&1; then
        READY=true
        break
    fi
    kill -0 "$TEMP_PID" 2>/dev/null || break
    sleep 1
done
[[ "$READY" == "true" ]] || die "OTP temporaneo non pronto: $BUILD_DIR/artifacts/otp-validate.log"

gql_temp() {
    curl -fsS -H 'Content-Type: application/json' \
        -d "$1" "http://127.0.0.1:$TEMP_PORT/otp/gtfs/v1"
}
FEEDS_JSON="$(gql_temp '{"query":"{ feeds { feedId } }"}')"
FEED_COUNT="$(jq '.data.feeds | length' <<<"$FEEDS_JSON")"
[[ "$FEED_COUNT" -ge 2 ]] || die "il nuovo grafo contiene $FEED_COUNT feed, attesi almeno 2"
ROUTES_JSON="$(gql_temp '{"query":"{ routes { gtfsId shortName } }"}')"
ROUTE_COUNT="$(jq '.data.routes | length' <<<"$ROUTES_JSON")"
EXPECTED_ROUTES=0
for key in "${!DB_SCHEMA[@]}"; do
    n="$(psql_query "SELECT count(DISTINCT route_id) FROM \"${DB_SCHEMA[$key]}\".trips;")"
    EXPECTED_ROUTES=$((EXPECTED_ROUTES + n))
done
# OTP does not expose routes without trips; compare against routes-with-trips.
[[ "$ROUTE_COUNT" == "$EXPECTED_ROUTES" ]] || die \
    "route nel grafo ($ROUTE_COUNT) diverse dalle route con corse nel database ($EXPECTED_ROUTES)"
for short_name in L1 C1 R7; do
    jq -e --arg name "$short_name" \
        'any(.data.routes[]; .shortName == $name)' <<<"$ROUTES_JSON" >/dev/null \
        || die "route $short_name assente dal nuovo grafo"
done

kill "$TEMP_PID" 2>/dev/null || true
wait "$TEMP_PID" 2>/dev/null || true
TEMP_PID=""

PREV_TARGET="$(readlink -f "$LIVE_LINK" 2>/dev/null || true)"
[[ -n "$PREV_TARGET" ]] || PREV_TARGET="/home/r0x4n/otp-1b-anm"
ln -sfn "$BUILD_DIR" "$LIVE_LINK.new"
mv -Tf "$LIVE_LINK.new" "$LIVE_LINK"
log "switch $LIVE_LINK -> $BUILD_DIR; riavvio $OTP_UNIT"
systemctl --user restart "$OTP_UNIT"
LIVE_READY=false
for _ in $(seq 1 90); do
    if curl -fsS "http://127.0.0.1:$LIVE_PORT/otp/" >/dev/null 2>&1; then
        LIVE_READY=true
        break
    fi
    sleep 1
done
if [[ "$LIVE_READY" != "true" ]]; then
    log "nuovo grafo non pronto; rollback a $PREV_TARGET"
    ln -sfn "$PREV_TARGET" "$LIVE_LINK.new"
    mv -Tf "$LIVE_LINK.new" "$LIVE_LINK"
    systemctl --user restart "$OTP_UNIT" || true
    die "health check fallito sul nuovo grafo; ripristinato $PREV_TARGET"
fi
LIVE_FEEDS="$(curl -fsS -H 'Content-Type: application/json' \
    -d '{"query":"{ feeds { feedId } }"}' \
    "http://127.0.0.1:$LIVE_PORT/otp/gtfs/v1" | jq '.data.feeds | length')"
[[ "$LIVE_FEEDS" -ge 2 ]] || die "feed mancanti sul servizio live dopo lo switch"

jq -n \
    --arg version "$BUILD_DIR" \
    --arg built_at "$(date --iso-8601=seconds)" \
    --arg graph_sha "$GRAPH_SHA" \
    --arg previous "$PREV_TARGET" \
    --arg unit "$OTP_UNIT" \
    --argjson port "$LIVE_PORT" \
    --argjson datasets "$DATASETS_JSON" \
    '{version: $version, built_at: $built_at, graph_sha256: $graph_sha,
      previous_version: $previous, unit: $unit, port: $port,
      datasets: $datasets}' > "$STATE_FILE.tmp"
mv -f "$STATE_FILE.tmp" "$STATE_FILE"
finish_success "grafo OTP aggiornato e attivo: $BUILD_DIR"
