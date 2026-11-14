-- 001: extensions. TimescaleDB comes preinstalled on Tiger Cloud; PostGIS has to be created.
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS postgis;
