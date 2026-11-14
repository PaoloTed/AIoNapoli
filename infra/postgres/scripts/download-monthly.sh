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
GTFS_URL="${GTFS_URL:-https://www2.anm.it/infoclick/infoclick.php?palina=3010}"
PBF_URL="${PBF_URL:-https://download.geofabrik.de/europe/italy/sud-latest.osm.pbf}"
GTFS_FALLBACK_URL="${GTFS_FALLBACK_URL:-https://www.anm.it/google/google-transit.zip}"
AUTO_IMPORT_GTFS="${AUTO_IMPORT_GTFS:-true}"
SKIP_PBF_DOWNLOAD="${SKIP_PBF_DOWNLOAD:-false}"

POSTGRES_DB="${POSTGRES_DB:-mobility}"
POSTGRES_USER="${POSTGRES_USER:-postgres}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-postgres}"
PGHOST="${PGHOST:-localhost}"
PGPORT="${PGPORT:-5432}"

DATE_TAG="$(date +%Y%m%d)"
OSM_DIR="$DATA_DIR/osm"
GTFS_DIR="$DATA_DIR/gtfs"
GTFS_CURRENT="$GTFS_DIR/current"

mkdir -p "$OSM_DIR" "$GTFS_DIR" "$GTFS_CURRENT"

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
    PBF_TARGET="$OSM_DIR/sud-latest.osm.pbf"
    PBF_ARCHIVE="$OSM_DIR/sud-${DATE_TAG}.osm.pbf"
    PBF_TMP="$OSM_DIR/sud-download.tmp"

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

if curl -fSL -k -A "Mozilla/5.0" --retry 3 --connect-timeout 30 -o "$GTFS_TMP" "$GTFS_URL"; then
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
            if curl -fSL -k -A "Mozilla/5.0" --retry 3 --connect-timeout 30 -o "$GTFS_TMP" "$GTFS_FALLBACK_URL"; then
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
    # 3. Extract and Ingest via gtfs-via-postgres (gtfs-to-sql)
    # -----------------------------------------------------------------------------
    if [ "$IS_VALID_ZIP" = "true" ]; then
        echo "[$(LOG_TIME)] [GTFS] Extracting $GTFS_LATEST_ZIP into $GTFS_CURRENT..."
        rm -rf "${GTFS_CURRENT:?}"/*
        unzip -o -q "$GTFS_LATEST_ZIP" -d "$GTFS_CURRENT"

        if [ "$AUTO_IMPORT_GTFS" = "true" ]; then
            if compgen -G "$GTFS_CURRENT/*.txt" > /dev/null; then
                echo "[$(LOG_TIME)] [GTFS] Found GTFS specification files (.txt). Starting gtfs-via-postgres import..."
                export PGPASSWORD="$POSTGRES_PASSWORD"

                # Wait if Postgres is still starting up
                for _ in {1..30}; do
                    if pg_isready -h "$PGHOST" -p "$PGPORT" -U "$POSTGRES_USER" >/dev/null 2>&1; then
                        break
                    fi
                    sleep 1
                done

                # Import using gtfs-to-sql piped into psql
                echo "[$(LOG_TIME)] [GTFS] Running: gtfs-to-sql --ignore-unsupported --trips-without-shape-id --stops-location-index $GTFS_CURRENT/*.txt | psql -h $PGHOST -p $PGPORT -U $POSTGRES_USER -d $POSTGRES_DB -b"
                if gtfs-to-sql --ignore-unsupported --trips-without-shape-id --stops-location-index "$GTFS_CURRENT"/*.txt | psql -h "$PGHOST" -p "$PGPORT" -U "$POSTGRES_USER" -d "$POSTGRES_DB" -b; then
                    echo "[$(LOG_TIME)] [GTFS] gtfs-via-postgres import completed successfully into database '$POSTGRES_DB'!"
                else
                    echo "[$(LOG_TIME)] [GTFS ERROR] gtfs-to-sql pipeline encountered an error during import." >&2
                fi
            else
                echo "[$(LOG_TIME)] [GTFS WARNING] No .txt files found inside the unzipped GTFS archive."
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
