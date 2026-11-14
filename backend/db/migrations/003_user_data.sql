-- 003: user data. Every table below `users` carries user_id = the Auth0 `sub`, and the backend
-- filters every query by it. ON DELETE CASCADE everywhere, so deleting a user row removes all
-- of their data ("delete my data").

CREATE TABLE users (
    id            text PRIMARY KEY,                  -- Auth0 sub
    display_name  text,
    language      text NOT NULL DEFAULT 'en',
    units         text NOT NULL DEFAULT 'metric',
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE farms (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     text NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    name        text NOT NULL DEFAULT 'My farm',
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX farms_user_idx ON farms (user_id);

CREATE TABLE fields (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     text NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    farm_id     uuid REFERENCES farms (id) ON DELETE CASCADE,
    name        text NOT NULL DEFAULT 'Field',
    geom        geometry(Geometry, 4326) NOT NULL,
    geom_hash   text NOT NULL,                       -- links to shared climate and feature rows
    area_ha     real,
    input_mode  text NOT NULL,                       -- 'geolocation' | 'point' | 'polygon' | 'browse'
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX fields_user_idx ON fields (user_id);
CREATE INDEX fields_geom_idx ON fields USING gist (geom);   -- region-wide alert matching

CREATE TABLE field_inputs (
    id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id            text NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    field_id           uuid NOT NULL REFERENCES fields (id) ON DELETE CASCADE,
    mode               text NOT NULL,                -- 'quick' | 'detailed' | 'exploring'
    answers            jsonb NOT NULL DEFAULT '{}',
    confirmed_prefill  jsonb NOT NULL DEFAULT '{}',
    created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX field_inputs_field_idx ON field_inputs (field_id);

CREATE TABLE rotations (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     text NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    field_id    uuid NOT NULL REFERENCES fields (id) ON DELETE CASCADE,
    name        text NOT NULL,
    is_current  boolean NOT NULL DEFAULT false,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX rotations_field_idx ON rotations (field_id);

CREATE TABLE rotation_steps (
    id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        text NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    rotation_id    uuid NOT NULL REFERENCES rotations (id) ON DELETE CASCADE,
    position       smallint NOT NULL,
    crop           text NOT NULL,
    plant_month    smallint CHECK (plant_month BETWEEN 1 AND 12),
    harvest_month  smallint CHECK (harvest_month BETWEEN 1 AND 12),
    notes          text,
    UNIQUE (rotation_id, position)
);

CREATE TABLE analyses (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       text NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    field_id      uuid NOT NULL REFERENCES fields (id) ON DELETE CASCADE,
    mode          text NOT NULL,
    request       jsonb NOT NULL,                    -- answers and report languages as sent
    result        jsonb NOT NULL,                    -- the full /analyze response
    top_strategy  text,                              -- for the "new findings" alert
    created_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX analyses_user_idx ON analyses (user_id);
CREATE INDEX analyses_field_idx ON analyses (field_id, created_at DESC);

CREATE TABLE strategy_results (
    id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       text NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    analysis_id   uuid NOT NULL REFERENCES analyses (id) ON DELETE CASCADE,
    strategy_key  text NOT NULL,                     -- 'current' | 'fill_bare' | 'break_pest' | 'save_water'
    name          text NOT NULL,
    rank          smallint NOT NULL,
    total_score   real NOT NULL,
    confidence    text NOT NULL,
    components    jsonb NOT NULL,                    -- score per component, with evidence objects
    UNIQUE (analysis_id, strategy_key)
);

-- One row per generated report. `question` is '' for the standard Tier 1 / Tier 2 report and
-- holds the farmer's question for a follow-up, so each answer is cached separately.
CREATE TABLE ai_reports (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         text NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    analysis_id     uuid NOT NULL REFERENCES analyses (id) ON DELETE CASCADE,
    tier            smallint NOT NULL CHECK (tier IN (1, 2)),
    language        text NOT NULL,
    language_level  text NOT NULL DEFAULT 'farmer',  -- 'farmer' | 'advanced'
    question        text NOT NULL DEFAULT '',
    content         jsonb NOT NULL,
    model           text NOT NULL,
    input_tokens    integer,
    output_tokens   integer,
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (analysis_id, tier, language, language_level, question)
);

CREATE TABLE pdf_reports (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      text NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    analysis_id  uuid NOT NULL REFERENCES analyses (id) ON DELETE CASCADE,
    language     text NOT NULL,
    file_path    text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now(),
    UNIQUE (analysis_id, language)
);

-- All alert types on by default.
CREATE TABLE alert_preferences (
    user_id      text NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    field_id     uuid NOT NULL REFERENCES fields (id) ON DELETE CASCADE,
    alert_types  text[] NOT NULL DEFAULT ARRAY[
                     'natural_event', 'fire', 'heavy_rain', 'drought', 'pest_risk', 'new_findings'
                 ],
    created_at   timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, field_id)
);

CREATE TABLE alerts (
    id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          text NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    field_id         uuid NOT NULL REFERENCES fields (id) ON DELETE CASCADE,
    type             text NOT NULL,                  -- one of the alert_types above
    severity         text NOT NULL,                  -- 'info' | 'watch' | 'warning'
    message          text NOT NULL,
    data             jsonb NOT NULL DEFAULT '{}',
    source           text NOT NULL,                  -- dataset, e.g. 'NASA EONET'
    source_event_id  text NOT NULL,                  -- source's event id, or a dated key for field checks
    triggered_at     timestamptz NOT NULL DEFAULT now(),
    read_at          timestamptz,
    UNIQUE (field_id, type, source_event_id)         -- one event never alerts a field twice
);
CREATE INDEX alerts_user_unread_idx ON alerts (user_id, triggered_at DESC) WHERE read_at IS NULL;
