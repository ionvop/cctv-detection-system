-- Migration: add direction to regions + rebuild aggregation_summaries
-- Run once against an existing database. Safe to re-run (uses IF NOT EXISTS / IF EXISTS).

-- 1. Add direction column to existing regions rows
ALTER TABLE regions ADD COLUMN IF NOT EXISTS direction VARCHAR(10) NOT NULL DEFAULT 'unknown';

-- 2. Refresh detection_street_view (regular view, safe to replace)
CREATE OR REPLACE VIEW detection_street_view AS
SELECT
    d.id            AS detection_id,
    d.cctv_id,
    d.video_id,
    d.track_id,
    d.object_type,
    d.confidence,
    d.x1,
    d.y1,
    d.x2,
    d.y2,
    d.time,
    dir.id          AS detection_in_region_id,
    r.id            AS region_id,
    r.direction,
    s.id            AS street_id,
    s.name          AS street_name,
    i.id            AS intersection_id,
    i.name          AS intersection_name
FROM detections            d
JOIN detections_in_regions dir ON dir.detection_id = d.id
JOIN regions               r   ON r.id  = dir.region_id
JOIN streets               s   ON s.id  = r.street_id
JOIN intersections         i   ON i.id  = s.intersection_id;

-- 3. Rebuild aggregation_summaries (continuous aggregate requires drop + recreate when GROUP BY changes)
SELECT remove_continuous_aggregate_policy('aggregation_summaries', if_not_exists => TRUE);
DROP MATERIALIZED VIEW IF EXISTS aggregation_summaries;

CREATE MATERIALIZED VIEW aggregation_summaries
WITH (timescaledb.continuous) AS
SELECT
    i.id                            AS intersection_id,
    s.id                            AS street_id,
    r.direction,
    d.object_type,
    time_bucket('1 minute', d.time) AS window_start,
    COUNT(*)                        AS count
FROM detections            d
JOIN detections_in_regions dir ON dir.detection_id = d.id
JOIN regions               r   ON r.id  = dir.region_id
JOIN streets               s   ON s.id  = r.street_id
JOIN intersections         i   ON i.id  = s.intersection_id
GROUP BY
    i.id,
    s.id,
    r.direction,
    d.object_type,
    time_bucket('1 minute', d.time)
WITH NO DATA;

SELECT add_continuous_aggregate_policy(
    'aggregation_summaries',
    start_offset      => INTERVAL '10 minutes',
    end_offset        => INTERVAL '30 seconds',
    schedule_interval => INTERVAL '30 seconds',
    if_not_exists     => TRUE
);

-- 4. Recreate indexes
CREATE INDEX IF NOT EXISTS idx_agg_intersection_window ON aggregation_summaries (intersection_id, window_start DESC);
CREATE INDEX IF NOT EXISTS idx_agg_street_window       ON aggregation_summaries (street_id,       window_start DESC);
CREATE INDEX IF NOT EXISTS idx_agg_direction           ON aggregation_summaries (direction);
