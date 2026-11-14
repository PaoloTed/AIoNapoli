-- Napoli Agentic City - Initial Schema (PostgreSQL 16 + PostGIS 3)
-- Source of truth: database/docs/SCHEMA.md

CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS schema_migrations (
    filename TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS zones (
    zone_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    geometry GEOGRAPHY(Polygon, 4326)
);

CREATE TABLE IF NOT EXISTS stops (
    stop_id TEXT PRIMARY KEY,
    stop_name TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    geometry GEOGRAPHY(Point, 4326) NOT NULL,
    source_id TEXT NOT NULL,
    data_reference TEXT NOT NULL,
    is_simulated BOOLEAN NOT NULL DEFAULT FALSE,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_stops_zone_id ON stops (zone_id);
CREATE INDEX IF NOT EXISTS idx_stops_geometry ON stops USING GIST (geometry);

CREATE TABLE IF NOT EXISTS routes (
    route_id TEXT PRIMARY KEY,
    route_short_name TEXT,
    route_type INTEGER NOT NULL,
    source_id TEXT NOT NULL,
    data_reference TEXT NOT NULL,
    is_simulated BOOLEAN NOT NULL DEFAULT FALSE,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS trips (
    trip_id TEXT PRIMARY KEY,
    route_id TEXT NOT NULL REFERENCES routes (route_id),
    service_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    data_reference TEXT NOT NULL,
    is_simulated BOOLEAN NOT NULL DEFAULT FALSE,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_trips_service_id ON trips (service_id);

CREATE TABLE IF NOT EXISTS stop_times (
    trip_id TEXT NOT NULL REFERENCES trips (trip_id),
    stop_id TEXT NOT NULL REFERENCES stops (stop_id),
    stop_sequence INTEGER NOT NULL,
    arrival_time INTERVAL,
    departure_time INTERVAL,
    source_id TEXT NOT NULL,
    data_reference TEXT NOT NULL,
    is_simulated BOOLEAN NOT NULL DEFAULT FALSE,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trip_id, stop_sequence)
);
CREATE INDEX IF NOT EXISTS idx_stop_times_stop_dep ON stop_times (stop_id, departure_time);

CREATE TABLE IF NOT EXISTS service_alerts (
    alert_id TEXT NOT NULL,
    route_id TEXT REFERENCES routes (route_id),
    stop_id TEXT REFERENCES stops (stop_id),
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ CHECK (valid_to IS NULL OR valid_to >= valid_from),
    source_id TEXT NOT NULL,
    confidence NUMERIC(3, 2) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    title TEXT NOT NULL,
    body TEXT,
    zone_id TEXT,
    is_simulated BOOLEAN NOT NULL DEFAULT FALSE,
    data_reference TEXT NOT NULL,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (source_id, alert_id)
);
CREATE INDEX IF NOT EXISTS idx_service_alerts_route_valid ON service_alerts (route_id, valid_from);
CREATE INDEX IF NOT EXISTS idx_service_alerts_zone_id ON service_alerts (zone_id);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    zone_id TEXT NOT NULL,
    geofence GEOGRAPHY(Polygon, 4326) NOT NULL,
    expected_attendance INTEGER NOT NULL CHECK (expected_attendance > 0),
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL CHECK (window_end > window_start),
    source_id TEXT NOT NULL,
    data_reference TEXT NOT NULL,
    is_simulated BOOLEAN NOT NULL DEFAULT TRUE,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_events_zone_window ON events (zone_id, window_start);
CREATE INDEX IF NOT EXISTS idx_events_geofence ON events USING GIST (geofence);

CREATE TABLE IF NOT EXISTS weather_snapshots (
    snapshot_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    snapshot_at TIMESTAMPTZ NOT NULL,
    forecast_at TIMESTAMPTZ NOT NULL,
    zone_id TEXT,
    precipitation_mm NUMERIC(6, 2),
    alert_level TEXT CHECK (alert_level IN ('verde', 'gialla', 'arancione', 'rossa')),
    heavy_rain BOOLEAN NOT NULL DEFAULT FALSE,
    expected_impact TEXT,
    source_id TEXT NOT NULL,
    data_reference TEXT NOT NULL,
    is_simulated BOOLEAN NOT NULL DEFAULT FALSE,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_id, zone_id, forecast_at)
);
CREATE INDEX IF NOT EXISTS idx_weather_latest ON weather_snapshots (source_id, zone_id, forecast_at);

CREATE TABLE IF NOT EXISTS occupancy_estimates (
    estimate_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    vehicle_id TEXT NOT NULL,
    line TEXT NOT NULL,
    occupancy_pct NUMERIC(5, 2) NOT NULL CHECK (occupancy_pct >= 0 AND occupancy_pct <= 100),
    observed_at TIMESTAMPTZ NOT NULL,
    source_id TEXT NOT NULL,
    data_reference TEXT NOT NULL,
    is_simulated BOOLEAN NOT NULL DEFAULT TRUE,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (vehicle_id, line, observed_at)
);
CREATE INDEX IF NOT EXISTS idx_occupancy_line_obs ON occupancy_estimates (line, observed_at);

CREATE TABLE IF NOT EXISTS vehicle_positions (
    vehicle_id TEXT NOT NULL,
    route_id TEXT REFERENCES routes (route_id),
    trip_id TEXT REFERENCES trips (trip_id),
    observed_at TIMESTAMPTZ NOT NULL,
    latitude NUMERIC(9, 6) NOT NULL,
    longitude NUMERIC(9, 6) NOT NULL,
    bearing NUMERIC(5, 2),
    speed_mps NUMERIC(5, 2),
    zone_id TEXT,
    source_id TEXT NOT NULL,
    data_reference TEXT NOT NULL,
    is_simulated BOOLEAN NOT NULL DEFAULT FALSE,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (vehicle_id, observed_at)
);
CREATE INDEX IF NOT EXISTS idx_vehicle_positions_route_obs ON vehicle_positions (route_id, observed_at);
CREATE INDEX IF NOT EXISTS idx_vehicle_positions_zone ON vehicle_positions (zone_id);

CREATE TABLE IF NOT EXISTS trip_updates (
    trip_id TEXT NOT NULL REFERENCES trips (trip_id),
    route_id TEXT REFERENCES routes (route_id),
    stop_id TEXT REFERENCES stops (stop_id),
    stop_sequence INTEGER,
    arrival_delay_s INTEGER CHECK (arrival_delay_s IS NULL OR arrival_delay_s > -3600),
    departure_delay_s INTEGER CHECK (departure_delay_s IS NULL OR departure_delay_s > -3600),
    schedule_relationship TEXT NOT NULL CHECK (schedule_relationship IN ('scheduled', 'skipped', 'canceled', 'no_data')),
    observed_at TIMESTAMPTZ NOT NULL,
    source_id TEXT NOT NULL,
    data_reference TEXT NOT NULL,
    is_simulated BOOLEAN NOT NULL DEFAULT FALSE,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (trip_id, stop_id, observed_at)
);
CREATE INDEX IF NOT EXISTS idx_trip_updates_trip_seq ON trip_updates (trip_id, stop_sequence);

CREATE TABLE IF NOT EXISTS ingestion_runs (
    run_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    connector TEXT NOT NULL CHECK (connector IN ('rss', 'gtfs', 'gtfs-rt', 'weather', 'events', 'occupancy')),
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NOT NULL,
    rows_written INTEGER NOT NULL,
    is_simulated BOOLEAN NOT NULL,
    outcome TEXT NOT NULL CHECK (outcome IN ('ok', 'fallback', 'failed')),
    detail TEXT
);

CREATE TABLE IF NOT EXISTS findings (
    finding_ref TEXT PRIMARY KEY,
    agent TEXT NOT NULL,
    type TEXT NOT NULL,
    severity TEXT NOT NULL,
    is_simulated BOOLEAN NOT NULL,
    payload JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS decisions (
    decision_id TEXT PRIMARY KEY,
    trigger_rule TEXT NOT NULL,
    conflict_detected BOOLEAN NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE VIEW v_weather_latest AS
SELECT w.*
FROM weather_snapshots w
INNER JOIN (
    SELECT source_id, COALESCE(zone_id, '') AS z, MAX(forecast_at) AS max_forecast
    FROM weather_snapshots
    GROUP BY source_id, COALESCE(zone_id, '')
) latest
ON w.source_id = latest.source_id
AND COALESCE(w.zone_id, '') = latest.z
AND w.forecast_at = latest.max_forecast;

CREATE OR REPLACE VIEW v_occupancy_latest AS
SELECT o.*
FROM occupancy_estimates o
INNER JOIN (
    SELECT vehicle_id, line, MAX(observed_at) AS max_obs
    FROM occupancy_estimates
    GROUP BY vehicle_id, line
) latest
ON o.vehicle_id = latest.vehicle_id
AND o.line = latest.line
AND o.observed_at = latest.max_obs;

CREATE OR REPLACE VIEW v_service_alerts_active AS
SELECT *
FROM service_alerts
WHERE valid_to IS NULL OR valid_to >= NOW();

CREATE OR REPLACE VIEW v_vehicle_positions_latest AS
SELECT v.*
FROM vehicle_positions v
INNER JOIN (
    SELECT vehicle_id, MAX(observed_at) AS max_obs
    FROM vehicle_positions
    WHERE observed_at >= NOW() - INTERVAL '90 seconds'
    GROUP BY vehicle_id
) latest
ON v.vehicle_id = latest.vehicle_id
AND v.observed_at = latest.max_obs;

CREATE OR REPLACE VIEW v_trip_updates_latest AS
SELECT t.*
FROM trip_updates t
INNER JOIN (
    SELECT trip_id, COALESCE(stop_id, '') AS s, MAX(observed_at) AS max_obs
    FROM trip_updates
    GROUP BY trip_id, COALESCE(stop_id, '')
) latest
ON t.trip_id = latest.trip_id
AND COALESCE(t.stop_id, '') = latest.s
AND t.observed_at = latest.max_obs;

