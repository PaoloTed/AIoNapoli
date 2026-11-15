#!/usr/bin/env bash
set -eo pipefail

# -----------------------------------------------------------------------------
# Monthly Download Script for GTFS & OpenStreetMap PBF
# Executed automatically on the 1st of every month via cron, or manually.
# -----------------------------------------------------------------------------

# Load environment if invoked by cron
if [ -f /etc/environment ]; then
    set -a
    # shellcheck disable=SC1091
    source /etc/environment 2>/dev/null || true
    set +a
fi

LOG_TIME() {
    date --iso-8601=seconds
}

echo "[$(LOG_TIME)] ==================================================="
echo "[$(LOG_TIME)] Starting scheduled monthly download pipeline..."
echo "[$(LOG_TIME)] ==================================================="

# Configurations & Defaults
DATA_DIR="${DATA_DIR:-/data}"
# GTFS_URL must point to a ZIP archive, never to the Infoclick HTML page.
GTFS_URL="${GTFS_URL:-https://www.anm.it/google/google-transit.zip}"
PBF_URL="${PBF_URL:-https://download.geofabrik.de/europe/italy/sud-latest.osm.pbf}"
GTFS_FALLBACK_URL="${GTFS_FALLBACK_URL:-}"
AUTO_IMPORT_GTFS="${AUTO_IMPORT_GTFS:-true}"
SKIP_PBF_DOWNLOAD="${SKIP_PBF_DOWNLOAD:-false}"
GTFS_SCHEMA="${GTFS_SCHEMA:-gtfs_anm}"
GTFS_DATASET_KEY="${GTFS_DATASET_KEY:-anm}"
GTFS_OPERATOR_ID="${GTFS_OPERATOR_ID:-ANM}"
GTFS_OPERATOR_NAME="${GTFS_OPERATOR_NAME:-Azienda Napoletana Mobilità}"
OTP_REBUILD_ENABLED="${OTP_REBUILD_ENABLED:-true}"
OTP_REBUILD_REQUEST_DIR="${OTP_REBUILD_REQUEST_DIR:-/data/otp-rebuild}"
SYNC_ERROR=0

POSTGRES_DB="${POSTGRES_DB:-mobility}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"

DATE_TAG="$(date +%Y%m%d)"
OSM_DIR="$DATA_DIR/osm"
GTFS_DIR="$DATA_DIR/gtfs"
mkdir -p "$OSM_DIR" "$GTFS_DIR"

PBF_TARGET="$OSM_DIR/sud-latest.osm.pbf"
PBF_ARCHIVE="$OSM_DIR/sud-${DATE_TAG}.osm.pbf"
PBF_TMP="$OSM_DIR/sud-download.tmp"

# -----------------------------------------------------------------------------
# 1. Download OpenStreetMap PBF (Geofabrik)
# -----------------------------------------------------------------------------
if [ "$SKIP_PBF_DOWNLOAD" = "true" ]; then
    echo "[$(LOG_TIME)] [OSM] SKIP_PBF_DOWNLOAD is set to true. Skipping PBF download."
elif [ -s "$PBF_TARGET" ] && [ "${FORCE_DOWNLOAD:-false}" != "true" ]; then
    echo "[$(LOG_TIME)] [OSM] PBF file already exists: $PBF_TARGET ($(du -h "$PBF_TARGET" | cut -f1)). Checking conditional update with server..."
    if curl -fSL -z "$PBF_TARGET" --retry 3 --connect-timeout 30 -o "$PBF_TMP" "$PBF_URL"; then
        if [ -s "$PBF_TMP" ]; then
            mv "$PBF_TMP" "$PBF_TARGET"
            cp -f "$PBF_TARGET" "$PBF_ARCHIVE" 2>/dev/null || true
            echo "[$(LOG_TIME)] [OSM] PBF updated to newer version."
        else
            echo "[$(LOG_TIME)] [OSM] PBF is up to date (304 Not Modified). No download needed."
            rm -f "$PBF_TMP"
        fi
    else
        echo "[$(LOG_TIME)] [OSM WARNING] Could not check update, keeping existing PBF."
        rm -f "$PBF_TMP"
    fi
else
    echo "[$(LOG_TIME)] [OSM] Downloading Southern Italy PBF from: $PBF_URL"

    # Use curl with:
    # -f (fail on HTTP error)
    # -sS (silent but show errors)
    # -L (follow HTTP redirects: geofabrik uses 307 redirect)
    # --retry 3 (retry on transient network errors)
    if curl -fSL --retry 3 --connect-timeout 30 -o "$PBF_TMP" "$PBF_URL"; then
        mv "$PBF_TMP" "$PBF_TARGET"
        cp -f "$PBF_TARGET" "$PBF_ARCHIVE" 2>/dev/null || true
        PBF_SIZE="$(du -h "$PBF_TARGET" | cut -f1)"
        echo "[$(LOG_TIME)] [OSM] PBF download successfully finished: $PBF_TARGET (Size: $PBF_SIZE)"
    else
        echo "[$(LOG_TIME)] [OSM ERROR] Failed to download PBF from $PBF_URL" >&2
        rm -f "$PBF_TMP"
    fi
fi

# -----------------------------------------------------------------------------
# 2. Download GTFS Data
# -----------------------------------------------------------------------------
echo "[$(LOG_TIME)] [GTFS] Fetching GTFS resource from: $GTFS_URL"
GTFS_DOWNLOAD="$GTFS_DIR/gtfs-download-${DATE_TAG}.bin"
GTFS_LATEST_ZIP="$GTFS_DIR/gtfs-latest.zip"
GTFS_TMP="$GTFS_DIR/gtfs-download.tmp"

IS_VALID_ZIP=false

if curl -fSL -A "Mozilla/5.0" --retry 3 --connect-timeout 30 -o "$GTFS_TMP" "$GTFS_URL"; then
    mv "$GTFS_TMP" "$GTFS_DOWNLOAD"
    DOWNLOAD_SIZE="$(du -h "$GTFS_DOWNLOAD" | cut -f1)"
    echo "[$(LOG_TIME)] [GTFS] Downloaded $DOWNLOAD_SIZE from $GTFS_URL"

    # Check whether the downloaded payload is a valid ZIP archive
    if unzip -tq "$GTFS_DOWNLOAD" >/dev/null 2>&1; then
        IS_VALID_ZIP=true
        cp -f "$GTFS_DOWNLOAD" "$GTFS_LATEST_ZIP"
        echo "[$(LOG_TIME)] [GTFS] Archive verified as valid ZIP format."
    else
        echo "[$(LOG_TIME)] [GTFS NOTICE] The resource downloaded from $GTFS_URL is NOT a ZIP archive."
        # If it's HTML, save it explicitly with .html extension for inspection
        if grep -qi "<html" "$GTFS_DOWNLOAD" 2>/dev/null; then
            echo "[$(LOG_TIME)] [GTFS NOTICE] The resource is an HTML document (e.g. Infoclick palina real-time view)."
            cp -f "$GTFS_DOWNLOAD" "$GTFS_DIR/infoclick-palina-3010-${DATE_TAG}.html"
            ln -sf "$GTFS_DIR/infoclick-palina-3010-${DATE_TAG}.html" "$GTFS_DIR/infoclick-latest.html"
        fi

        # Check if a fallback GTFS archive URL was provided
        if [ -n "$GTFS_FALLBACK_URL" ]; then
            echo "[$(LOG_TIME)] [GTFS] Trying fallback GTFS archive URL: $GTFS_FALLBACK_URL"
            if curl -fSL -A "Mozilla/5.0" --retry 3 --connect-timeout 30 -o "$GTFS_TMP" "$GTFS_FALLBACK_URL"; then
                if unzip -tq "$GTFS_TMP" >/dev/null 2>&1; then
                    mv "$GTFS_TMP" "$GTFS_LATEST_ZIP"
                    IS_VALID_ZIP=true
                    echo "[$(LOG_TIME)] [GTFS] Fallback archive downloaded and verified as valid ZIP."
                else
                    echo "[$(LOG_TIME)] [GTFS WARNING] Fallback URL did not return a valid ZIP archive."
                    rm -f "$GTFS_TMP"
                fi
            fi
        fi
    fi

    # -----------------------------------------------------------------------------
    # 3. Controlled import into the dedicated GTFS schema
    # -----------------------------------------------------------------------------
    if [ "$IS_VALID_ZIP" = "true" ]; then
        if [ "$AUTO_IMPORT_GTFS" = "true" ]; then
            export PGPASSWORD="$POSTGRES_PASSWORD"
            export PGUSER="$POSTGRES_USER"
            export PGDATABASE="$POSTGRES_DB"

            # Wait if Postgres is still starting up
            for _ in {1..30}; do
                if pg_isready -h "$PGHOST" -p "$PGPORT" -U "$POSTGRES_USER" >/dev/null 2>&1; then
                    break
                fi
                sleep 1
            done

            IMPORT_SCRIPT="${GTFS_IMPORT_SCRIPT:-/usr/local/bin/import-gtfs.sh}"
            if [ ! -x "$IMPORT_SCRIPT" ]; then
                IMPORT_SCRIPT="$(cd "$(dirname "$0")/.." && pwd)/import-gtfs.sh"
            fi

            echo "[$(LOG_TIME)] [GTFS] Starting controlled import: $GTFS_LATEST_ZIP -> $GTFS_SCHEMA"
            if bash "$IMPORT_SCRIPT" \
                --zip "$GTFS_LATEST_ZIP" \
                --dataset-key "$GTFS_DATASET_KEY" \
                --schema "$GTFS_SCHEMA" \
                --operator-id "$GTFS_OPERATOR_ID" \
                --operator-name "$GTFS_OPERATOR_NAME" \
                --source-url "$GTFS_URL" \
                --publish; then
                echo "[$(LOG_TIME)] [GTFS] import completed into schema '$GTFS_SCHEMA'."

                SOURCE_SHA256="$(sha256sum "$GTFS_LATEST_ZIP" | awk '{print $1}')"
                DB_ROW="$(
                    psql -h "$PGHOST" -p "$PGPORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
                        -X -t -A -F '|' -c \
                        "SELECT source_sha256, gtfs_schema, COALESCE(service_start::text, ''), COALESCE(service_end::text, '')
                         FROM public.gtfs_datasets
                         WHERE dataset_key = '$GTFS_DATASET_KEY' AND is_active
                         ORDER BY published_at DESC LIMIT 1;"
                )"
                IFS='|' read -r DB_SHA256 DB_SCHEMA DB_SERVICE_START DB_SERVICE_END <<<"$DB_ROW"
                DB_IMPORT_ID="$(
                    psql -h "$PGHOST" -p "$PGPORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
                        -X -t -A -c \
                        "SELECT import_id FROM public.gtfs_imports
                         WHERE dataset_key = '$GTFS_DATASET_KEY' AND status = 'published'
                         ORDER BY import_id DESC LIMIT 1;"
                )"
                if [ -z "$DB_SHA256" ] || [ "$DB_SHA256" != "$SOURCE_SHA256" ] || [ "$DB_SCHEMA" != "$GTFS_SCHEMA" ]; then
                    echo "[$(LOG_TIME)] [GTFS ERROR] pubblicazione DB non coerente: file=$SOURCE_SHA256 db=${DB_SHA256:-assente} schema=${DB_SCHEMA:-assente}." >&2
                    SYNC_ERROR=1
                elif [ "$OTP_REBUILD_ENABLED" = "true" ]; then
                    mkdir -p "$OTP_REBUILD_REQUEST_DIR"
                    chmod 0777 "$OTP_REBUILD_REQUEST_DIR" 2>/dev/null || true
                    REQUEST_ID="$(date -u +%Y%m%dT%H%M%SZ)-$$"
                    REQUEST_TMP="$OTP_REBUILD_REQUEST_DIR/.request-${REQUEST_ID}.tmp"
                    cat > "$REQUEST_TMP" <<EOF
{
  "request_id": "${REQUEST_ID}",
  "requested_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "dataset_key": "${GTFS_DATASET_KEY}",
  "gtfs_schema": "${DB_SCHEMA}",
  "zip_path": "${GTFS_LATEST_ZIP}",
  "source_sha256": "${SOURCE_SHA256}",
  "service_start": "${DB_SERVICE_START}",
  "service_end": "${DB_SERVICE_END}",
  "import_id": "${DB_IMPORT_ID}"
}
EOF
                    mv -f "$REQUEST_TMP" "$OTP_REBUILD_REQUEST_DIR/request.json"
                    echo "[$(LOG_TIME)] [OTP] richiesta di ricostruzione grafo scritta in $OTP_REBUILD_REQUEST_DIR/request.json (richiesta $REQUEST_ID)."
                else
                    echo "[$(LOG_TIME)] [OTP] OTP_REBUILD_ENABLED=false: grafo non ricostruito."
                fi
            else
                echo "[$(LOG_TIME)] [GTFS ERROR] controlled import failed." >&2
            fi
        else
            echo "[$(LOG_TIME)] [GTFS] AUTO_IMPORT_GTFS is false. Skipping automated database import."
        fi
    else
        echo "[$(LOG_TIME)] [GTFS] Skipping database import since no valid GTFS ZIP archive was retrieved."
        echo "[$(LOG_TIME)] [GTFS TIP] You can supply a valid GTFS zip URL via GTFS_URL or GTFS_FALLBACK_URL environment variables."
    fi
else
    echo "[$(LOG_TIME)] [GTFS ERROR] Download request failed for $GTFS_URL" >&2
    rm -f "$GTFS_TMP"
fi

echo "[$(LOG_TIME)] ==================================================="
echo "[$(LOG_TIME)] Monthly download task finished."
echo "[$(LOG_TIME)] ==================================================="
exit "$SYNC_ERROR"
