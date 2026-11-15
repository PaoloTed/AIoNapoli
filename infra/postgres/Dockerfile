FROM ubuntu:24.04

LABEL maintainer="Hackathon 2026 CDS"
LABEL description="Ubuntu Server with PostgreSQL 18, PostGIS, GTFS/OSM controlled ingestion"

ENV DEBIAN_FRONTEND=noninteractive \
    TZ=UTC \
    PGVERSION=18 \
    PGDATA=/var/lib/postgresql/18/main \
    PATH=/usr/lib/postgresql/18/bin:$PATH

# 1. Install base utilities and system requirements
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    locales \
    cron \
    unzip \
    file \
    procps \
    osm2pgsql \
    osmium-tool \
    && rm -rf /var/lib/apt/lists/*

# Set UTF-8 locale
RUN locale-gen en_US.UTF-8 && update-locale LANG=en_US.UTF-8
ENV LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8

# 2. Add PostgreSQL official PGDG repository for Ubuntu 24.04 (noble)
RUN install -d /etc/apt/keyrings && \
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc | gpg --dearmor -o /etc/apt/keyrings/postgresql.gpg && \
    echo "deb [signed-by=/etc/apt/keyrings/postgresql.gpg] http://apt.postgresql.org/pub/repos/apt noble-pgdg main" > /etc/apt/sources.list.d/pgdg.list

# 3. Install PostgreSQL 18 & PostGIS 3
RUN apt-get update && apt-get install -y --no-install-recommends \
    postgresql-18 \
    postgresql-client-18 \
    postgresql-18-postgis-3 \
    postgresql-18-postgis-3-scripts \
    postgis \
    && rm -rf /var/lib/apt/lists/*

# 4. Install Node.js 22 LTS and a pinned gtfs-via-postgres
ARG GTFS_VIA_POSTGRES_VERSION=4.13.0
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g "gtfs-via-postgres@${GTFS_VIA_POSTGRES_VERSION}" && \
    rm -rf /var/lib/apt/lists/*

# 5. Create storage directories
RUN mkdir -p /data/gtfs /data/osm /var/log/postgresql /var/run/postgresql "$PGDATA" && \
    chown -R postgres:postgres /var/run/postgresql /var/log/postgresql "$PGDATA"

# 6. Install Cron task & execution scripts
COPY crontab /etc/cron.d/monthly-downloads
COPY scripts/download-monthly.sh /usr/local/bin/download-monthly.sh
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
COPY import-gtfs.sh /usr/local/bin/import-gtfs.sh
COPY gtfs-metadata.sql /usr/local/share/gtfs-metadata.sql
COPY import-osm.sh /usr/local/bin/import-osm.sh
COPY osm-territory.lua /usr/local/share/osm-territory.lua
COPY osm-territory.sql /usr/local/share/osm-territory.sql
COPY sync-gtfs-refs.sql /usr/local/share/sync-gtfs-refs.sql
COPY sync-osm-refs.sql /usr/local/share/sync-osm-refs.sql

RUN chmod 0644 /etc/cron.d/monthly-downloads && \
    crontab /etc/cron.d/monthly-downloads && \
    chmod +x /usr/local/bin/download-monthly.sh /usr/local/bin/entrypoint.sh \
             /usr/local/bin/import-gtfs.sh /usr/local/bin/import-osm.sh

# 7. Environment variable defaults
ENV POSTGRES_DB=mobility \
    POSTGRES_USER=postgres \
    POSTGRES_PASSWORD=postgres \
    GTFS_URL="https://www.anm.it/google/google-transit.zip" \
    GTFS_SCHEMA=gtfs_anm \
    GTFS_DATASET_KEY=anm \
    GTFS_OPERATOR_ID=ANM \
    GTFS_OPERATOR_NAME="Azienda Napoletana Mobilità" \
    GTFS_DATASETS=eav:gtfs_eav,anm:gtfs_anm \
    OTP_REBUILD_ENABLED=true \
    OTP_REBUILD_REQUEST_DIR=/data/otp-rebuild \
    PBF_URL="https://download.geofabrik.de/europe/italy/sud-latest.osm.pbf" \
    RUN_ON_STARTUP=true \
    AUTO_IMPORT_GTFS=true

EXPOSE 5432

VOLUME ["/var/lib/postgresql", "/data"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
