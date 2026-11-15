-- 005: what accounts and alert delivery need (steps 3.4 and 4.2-4.3).

-- The verified email from Auth0 (alert emails only; never shown to other users).
ALTER TABLE users
    ADD COLUMN email             text,
    ADD COLUMN last_alert_check  timestamptz;   -- "check when the app opens", cached ~6 hours

-- Per field: which channels deliver its alerts (in-app is always on).
ALTER TABLE alert_preferences
    ADD COLUMN email  boolean NOT NULL DEFAULT true,
    ADD COLUMN push   boolean NOT NULL DEFAULT true;

-- Delivery bookkeeping, so an alert is emailed / pushed once.
ALTER TABLE alerts
    ADD COLUMN emailed_at  timestamptz,
    ADD COLUMN pushed_at   timestamptz;

-- Browser push subscriptions (Web Push). One user can have several devices.
CREATE TABLE push_subscriptions (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     text NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    endpoint    text NOT NULL UNIQUE,
    p256dh      text NOT NULL,
    auth        text NOT NULL,
    created_at  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX push_subscriptions_user_idx ON push_subscriptions (user_id);

-- Region-wide events seen by any check (EONET), so the background job and simulations can
-- match them against every saved field. Shared data: no personal information.
CREATE TABLE natural_events (
    id           text PRIMARY KEY,               -- EONET event id, or 'SIM-...' for simulations
    title        text NOT NULL,
    category     text NOT NULL,
    geom         geometry(Geometry, 4326) NOT NULL,
    event_date   timestamptz,
    source_url   text,
    simulated    boolean NOT NULL DEFAULT false,
    seen_at      timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX natural_events_geom_idx ON natural_events USING gist (geom);
