FROM ubuntu:24.04

LABEL maintainer="Hackathon 2026 CDS"
LABEL description="Ubuntu Server with PostgreSQL 18, PostGIS, gtfs-via-postgres, and monthly GTFS/PBF ingestion"

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

# 4. Install Node.js 22 LTS and gtfs-via-postgres
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    npm install -g gtfs-via-postgres && \
    ln -sf $(which gtfs-to-sql) /usr/local/bin/gtfs-via-postgres && \
    rm -rf /var/lib/apt/lists/*

# 5. Create storage directories
RUN mkdir -p /data/gtfs /data/osm /var/log/postgresql /var/run/postgresql "$PGDATA" && \
    chown -R postgres:postgres /var/run/postgresql /var/log/postgresql "$PGDATA"

# 6. Install Cron task & execution scripts
COPY crontab /etc/cron.d/monthly-downloads
COPY scripts/download-monthly.sh /usr/local/bin/download-monthly.sh
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh

RUN chmod 0644 /etc/cron.d/monthly-downloads && \
    crontab /etc/cron.d/monthly-downloads && \
    chmod +x /usr/local/bin/download-monthly.sh /usr/local/bin/entrypoint.sh

# 7. Environment variable defaults
ENV POSTGRES_DB=mobility \
    POSTGRES_USER=postgres \
    POSTGRES_PASSWORD=postgres \
    GTFS_URL="https://www2.anm.it/infoclick/infoclick.php?palina=3010" \
    PBF_URL="https://download.geofabrik.de/europe/italy/sud-latest.osm.pbf" \
    RUN_ON_STARTUP=true \
    AUTO_IMPORT_GTFS=true

EXPOSE 5432

VOLUME ["/var/lib/postgresql", "/data"]

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
