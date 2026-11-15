-- 004: crop trait columns the engine scores on, and pest-rule metadata shown in alerts.
ALTER TABLE crops
    ADD COLUMN heat_tolerance          text,   -- 'low' | 'medium' | 'high'
    ADD COLUMN drought_tolerance       text,
    ADD COLUMN waterlogging_tolerance  text,
    ADD COLUMN labor_need              text,
    ADD COLUMN notes                   text;

ALTER TABLE pest_rules
    ADD COLUMN kind        text,               -- 'disease' | 'insect'
    ADD COLUMN source_url  text;
