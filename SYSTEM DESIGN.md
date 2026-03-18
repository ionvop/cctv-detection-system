# System Design Document

## Overview 

The system runs entirely on the city's own server infrastructure. No footage or data is sent to external cloud services. Camera feeds are processed and discarded in real time and the system stores only the results of its analysis, not the video itself

## Architecture

```

┌─────────────────────────────────────┐
│           CCTV Layer                │
│  Cam 1   Cam 2   Cam 3  ...  Cam N  │
└────────────────┬────────────────────┘
                 │ RTSP streams
┌────────────────▼────────────────────┐
│           Worker Pool               │
│  W1      W2      W3    ...   WN     │
│  (YOLOv8 inference per camera)      │
└────────────────┬────────────────────┘
                 │ batch inserts
┌────────────────▼────────────────────┐
│           PgBouncer                 │
│       (connection pooling)          │
└────────────────┬────────────────────┘
                 │
┌────────────────▼────────────────────┐
│     PostgreSQL + TimescaleDB        │
│  detections (hypertable)            │
│  aggregation_summaries (cont. agg)  │
│  cctvs, intersections, heartbeats   │
└────────────────┬────────────────────┘
                 │               
        ┌────────▼──────────┐    
        │       API         │    
        │   REST + SSE      │    
        └────────┬──────────┘  
                 │                      
┌────────────────▼──────────────────────────┐
│              Frontend                     │
│   Live dashboard via SSE + REST reports   │
└───────────────────────────────────────────┘
```

## Component Breakdown

### Worker

Each worker claims one camera from the database at startup using a lock, connects directly to its RTSP stream, runs YOLOv8 inference on each frame, and batch-writes detections to the database every 100-500ms. It sends a heartbeat every 3-5 seconds to maintain its camera claim. If the camera goes offline it keeps heartbeating and retrying the stream until it recovers.


### API

Exposes REST endpoints for historical trend queries and an SSE endpoint for real-time dashboard updates. The SSE push runs one query against `aggregation_summaries` every 5-10 seconds and fans the result to all connected clients simultaneously (this avoids recreating http requests, much more efficient than websockets, also no need for full duplex because this is only server-to-client).


### Database (PostgreSQL + TimescaleDB)

PostgreSQL is the single store for all system data. The `detections` table runs as a TimescaleDB hypertable partitioned into hourly chunks. It contains the `aggregation_summaries`, which is a continuous aggregate view that TimescaleDB. Raw detections are purged after 72 hours; summaries are kept indefinitely (the data will get too big if not handled, so minute view of the data are sacrificed).


### PgBouncer

Sits between all services and PostgreSQL, multiplexing up to 1,000 worker connections into a small stable pool of 20-50 actual database connections. (TODO: check if it's possible to use the PostgreSQL Pooling here) 


### Frontend

A web dashboard showing real-time intersection counts via SSE and historical trend charts via REST. 


## Database Schema


### intersections

Represents a physical intersection in the city. Multiple cameras can belong to the same intersection. Used to group detection data for aggregation and deduplication.

```sql
CREATE TABLE intersections (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(255) NOT NULL,
    latitude    FLOAT,
    longitude   FLOAT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

### cctvs

Represents a physical camera. Stores the RTSP stream key used by the worker to connect, the current operational status, and which intersection the camera belongs to.

```sql
CREATE TABLE cctvs (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL,
    stream_key      VARCHAR(255) NOT NULL,
    status          VARCHAR(50)  NOT NULL DEFAULT 'offline',
    intersection_id INTEGER REFERENCES intersections(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
```

---

### worker_heartbeats

One row per camera. Tracks which worker process currently owns each camera, when it last checked in, and its current status. Used by spare workers to find unclaimed or abandoned cameras, and by the monitor to detect dead workers.

```sql
CREATE TABLE worker_heartbeats (
    id                SERIAL PRIMARY KEY,
    cctv_id           INTEGER NOT NULL UNIQUE REFERENCES cctvs(id) ON DELETE CASCADE,
    worker_pid        INTEGER NOT NULL,
    last_seen         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claimed_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status            VARCHAR(50) NOT NULL DEFAULT 'running',
    frames_per_second FLOAT
);
```

---

### detections

One row per detected object per frame. Stored as a TimescaleDB hypertable partitioned by `detected_at` in hourly chunks. Retained for 72 hours then automatically purged.

```sql
CREATE TABLE detections (
    id              SERIAL PRIMARY KEY,
    cctv_id         INTEGER NOT NULL REFERENCES cctvs(id) ON DELETE CASCADE,
    intersection_id INTEGER REFERENCES intersections(id) ON DELETE SET NULL,
    detected_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    object_type     VARCHAR(50) NOT NULL,
    confidence      FLOAT NOT NULL,
    x1              FLOAT NOT NULL,
    y1              FLOAT NOT NULL,
    x2              FLOAT NOT NULL,
    y2              FLOAT NOT NULL
);

SELECT create_hypertable('detections', 'detected_at', chunk_time_interval => INTERVAL '1 hour');
SELECT add_retention_policy('detections', INTERVAL '72 hours');
```

---

## Workflows

### 1.1 Worker startup - camera claim

1. Worker pod starts with no assigned identity.
2. Worker queries `cctvs` left joined with `worker_heartbeats` for any camera where no heartbeat row exists or `worker_heartbeats.last_seen` is older than 15 seconds.
3. Worker issues `SELECT FOR UPDATE` on the target `cctvs` row - this locks it so no other worker can claim it simultaneously (avoid race condition).
4. Worker upserts into `worker_heartbeats` - writes its `worker_pid`, current timestamp for `last_seen` and `claimed_at`, status as `running`.
5. Lock releases.
6. Worker reads `cctvs.stream_key` and `cctvs.intersection_id` from the claimed row.
7. Worker opens RTSP connection to the stream key and enters the processing loop.
8. If no unclaimed camera is found, worker polls every 5 seconds until one becomes available - this is the idle spare worker behavior.

---

### 1.2 Worker processing loop

1. Worker pulls the next frame from its RTSP stream.
2. YOLOv8 runs inference and returns detected objects - each with `object_type`, `confidence`, and bounding box `x1 y1 x2 y2`.
3. Worker appends each detection to an in-memory buffer.
4. Every 100-500ms, worker flushes the buffer with a single batch INSERT into `detections` (batch insert here because of the sheer amount of data and also the additional overhead if inserted one by one).
5. Every 3-5 seconds, separately, worker updates `worker_heartbeats.last_seen` and `frames_per_second` with a single UPDATE by `cctv_id`.
6. Repeat from step 1 immediately.

---

### 1.3 Camera goes offline

1. RTSP connection drops. Worker catches the error.
2. Worker updates `worker_heartbeats.status` to `reconnecting`.
3. Worker updates `cctvs.status` to `offline`.
4. Worker stops buffering and writing detections.
5. Worker continues writing heartbeats every 3-5 seconds - claim stays alive, no spare worker will steal this camera.
6. Worker retries RTSP connection with exponential backoff.
7. When stream recovers: worker reconnects, updates `worker_heartbeats.status` to `running`, updates `cctvs.status` to `active`, resumes processing loop from 1.2 step 1.

---

### 1.4 Worker dies (if naay 1000 ka cctv, mag run ta ug 1100 para maximum uptime)

1. Worker process crashes. `worker_heartbeats.last_seen` stops updating.
2. After 15 seconds, a spare worker's next scan finds this stale heartbeat row.
3. Spare worker issues `SELECT FOR UPDATE` on the orphaned `cctvs` row.
4. Spare worker overwrites `worker_heartbeats` - its own `worker_pid`, fresh `claimed_at`, fresh `last_seen`, status `running`.
5. Spare worker reads `stream_key` and `intersection_id`, opens RTSP connection, begins processing.
6. Gap in detections for that camera: at most 15 seconds plus spare worker's next poll interval. Acceptable for trend reporting.
7. Kubernetes simultaneously restarts the dead pod. When it comes back it scans for unclaimed cameras and joins the idle spare pool.

---

### 1.5 Adding a new camera

1. Operator inserts a row into `intersections` if this is a new intersection.
2. Operator inserts a row into `cctvs` with the camera's name, stream key, and intersection ID. Status defaults to `offline`. No `worker_heartbeats` row exists yet.
3. Within 5 seconds, a spare worker's polling loop finds this unclaimed camera.
4. Spare worker claims it via `SELECT FOR UPDATE`, writes to `worker_heartbeats`, reads `stream_key`, connects to RTSP stream.
5. `cctvs.status` updates to `active`.
6. Zero changes to Kubernetes. Zero changes to any existing worker. Zero downtime.
7. If no spare workers are available, operator increases the Kubernetes deployment replica count. New generic pods spin up and claim the new cameras.

---

### 1.6 Aggregation

As detections land in the hypertable, TimescaleDB tracks which 1-minute time buckets have received new data. Every minute it processes only the new detections since the last refresh and updates the counts. 

---

### 1.7 SSE push to frontend

1. Frontend client connects to the SSE endpoint.
2. API opens a persistent HTTP connection.
3. Every 5-10 seconds, API executes one query against `aggregation_summaries` joined with `intersections` - fetching the latest minute bucket per intersection.
4. Result is serialized and pushed to all connected SSE clients simultaneously in a single fan-out.
5. Frontend re-renders the dashboard.
6. Historical queries (trend charts, daily summaries) hit `aggregation_summaries` via standard REST endpoints filtered by `intersection_id` and `window_start` range. The raw `detections` table is never queried by the API under any circumstance.

---

## Failure Modes and Recovery

| Failure | Detection | Recovery | Human action needed | Impact |
|---|---|---|---|---|
| Camera goes offline | Worker catches dropped RTSP connection immediately | Worker retries with backoff; auto-resumes when camera recovers | None (outside of scope) | No detections for that camera during outage |
| Worker process crashes | Spare worker detects stale heartbeat after 15 seconds | Spare worker claims orphaned camera automatically; Kubernetes restarts dead pod | None | Up to 15-second gap in detections for one camera |
| Worker stuck (alive but not processing) | Stale heartbeat detected by spare worker after 15 seconds | Heartbeat expiry allows spare worker to claim camera | None | Up to 15-second gap in detections for one camera |
| All spare workers exhausted | New camera added but no idle worker available | Operator scales Kubernetes replica count | Scale up worker deployment | New camera not processed until scaled |