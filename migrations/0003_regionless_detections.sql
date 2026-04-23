-- Migration 0003: make regions optional
-- Detections on cameras without regions now appear at intersection level
-- (street_id IS NULL, direction = 'unknown') in aggregation_summaries.

-- 1. Rebuild detection_street_view with LEFT JOINs
DROP VIEW IF EXISTS detection_street_view CASCADE;
CREATE VIEW detection_street_view AS
SELECT
    d.id            AS detection_id,
    d.cctv_id,
    d.video_id,
    d.track_id,
    d.object_type,
    d.confidence,
    d.x1, d.y1, d.x2, d.y2,
    d.time,
    dir.id                              AS detection_in_region_id,
    r.id                                AS region_id,
    COALESCE(r.direction, 'unknown')    AS direction,
    s.id                                AS street_id,
    s.name                              AS street_name,
    i.id                                AS intersection_id,
    i.name                              AS intersection_name
FROM detections d
JOIN cctvs c ON c.id = d.cctv_id
JOIN intersections i ON i.id = c.intersection_id
LEFT JOIN detections_in_regions dir ON dir.detection_id = d.id
LEFT JOIN regions r ON r.id = dir.region_id
LEFT JOIN streets s ON s.id = r.street_id;

-- 2. Rebuild aggregation_summaries with LEFT JOINs
SELECT remove_continuous_aggregate_policy('aggregation_summaries', if_not_exists => TRUE);
DROP MATERIALIZED VIEW IF EXISTS aggregation_summaries;

CREATE MATERIALIZED VIEW aggregation_summaries
WITH (timescaledb.continuous) AS
SELECT
    i.id                                AS intersection_id,
    i.name                              AS intersection_name,
    s.id                                AS street_id,
    COALESCE(r.direction, 'unknown')    AS direction,
    d.object_type,
    time_bucket('1 minute', d.time)     AS window_start,
    COUNT(*)::int                       AS count
FROM detections d
JOIN cctvs c ON c.id = d.cctv_id
JOIN intersections i ON i.id = c.intersection_id
LEFT JOIN detections_in_regions dir ON dir.detection_id = d.id
LEFT JOIN regions r ON r.id = dir.region_id
LEFT JOIN streets s ON s.id = r.street_id
GROUP BY i.id, i.name, s.id, COALESCE(r.direction, 'unknown'), d.object_type,
         time_bucket('1 minute', d.time)
WITH NO DATA;

SELECT add_continuous_aggregate_policy('aggregation_summaries',
    start_offset      => INTERVAL '1 hour',
    end_offset        => INTERVAL '10 seconds',
    schedule_interval => INTERVAL '30 seconds');

CREATE INDEX IF NOT EXISTS idx_agg_intersection ON aggregation_summaries (intersection_id, window_start DESC);
CREATE INDEX IF NOT EXISTS idx_agg_street       ON aggregation_summaries (street_id, window_start DESC);
CREATE INDEX IF NOT EXISTS idx_agg_window       ON aggregation_summaries (window_start DESC);

-- Backfill
CALL refresh_continuous_aggregate('aggregation_summaries', NULL, NULL);
