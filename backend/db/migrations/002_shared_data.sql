-- 002: shared data. No personal information here. Rows that belong to a location are keyed by
-- geom_hash (computed by the backend from the field geometry), never by user.

-- Cached responses from outside APIs (POWER, Earth Engine, EONET, FIRMS, ...).
CREATE TABLE data_cache (
    key         text PRIMARY KEY,
    namespace   text NOT NULL,                       -- e.g. 'power', 'earthengine'
    geom_hash   text,                                -- set when the entry belongs to one location
    value       jsonb NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now(),
    updated_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX data_cache_geom_hash_idx ON data_cache (geom_hash) WHERE geom_hash IS NOT NULL;

-- Daily climate per location, one row per (location, variable, day). TimescaleDB hypertable
-- with 1-year chunks (30 years of daily data = 30 chunks, not ~1,500 with the 7-day default).
-- Columnstore stays off for now so backfilling past years never writes into compressed chunks.
CREATE TABLE climate_daily (
    geom_hash  text NOT NULL,
    variable   text NOT NULL,                        -- e.g. POWER 'T2M', 'PRECTOTCORR'
    day        date NOT NULL,
    value      real,                                 -- NULL when the source has no value
    unit       text NOT NULL,
    source     text NOT NULL,                        -- e.g. 'NASA POWER'
    PRIMARY KEY (geom_hash, variable, day)
) WITH (
    tsdb.hypertable = true,
    tsdb.partition_column = 'day',
    tsdb.chunk_interval = '1 year',
    tsdb.columnstore = false
);

-- Monthly features per location (harmonizer output, step 1.4).
-- year = 0 marks the long-term climatology for that month; anomaly = value - climatology.
CREATE TABLE field_monthly_features (
    geom_hash          text NOT NULL,
    variable           text NOT NULL,
    year               smallint NOT NULL,            -- 0 = climatology baseline
    month              smallint NOT NULL CHECK (month BETWEEN 1 AND 12),
    value              real,
    anomaly            real,
    unit               text NOT NULL,
    source             text NOT NULL,
    native_resolution  text NOT NULL,
    period             text NOT NULL,                -- e.g. '1991-2020' or '2024'
    computed_at        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (geom_hash, variable, year, month)
);

-- Crop climate and soil ranges (FAO ECOCROP) plus rotation traits (team-curated). Step 1.5.
CREATE TABLE crops (
    name             text PRIMARY KEY,               -- common English name, e.g. 'mungbean'
    scientific_name  text,
    family           text,                           -- plant family, for pest-cycle breaks
    is_legume        boolean,
    root_depth_m     real,
    cover_crop_role  text,
    forage           boolean,
    water_need       text,                           -- 'low' | 'medium' | 'high'
    ecocrop          jsonb NOT NULL DEFAULT '{}',    -- ECOCROP ranges: temperature, rain, pH, cycle
    traits_source    text,                           -- citation for the team-curated traits
    updated_at       timestamptz NOT NULL DEFAULT now()
);

-- Weather conditions that favor pests and diseases. Team-curated; every rule cites a source.
CREATE TABLE pest_rules (
    id           serial PRIMARY KEY,
    pest         text NOT NULL,
    crops        text[] NOT NULL DEFAULT '{}',
    description  text NOT NULL,                      -- plain words, e.g. '3+ days above 90% humidity'
    rule         jsonb NOT NULL,                     -- machine-readable thresholds
    source       text NOT NULL,
    UNIQUE (pest, description)
);
