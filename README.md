# CCTV Detection System

A simple CCTV detection system built with **FastAPI**, **MySQL**, and **YOLOv8**.

The project consists of two components:

1. **Server** – REST API for managing CCTV cameras and retrieving detection data.
2. **Worker** – A computer vision worker that reads video from a webcam, runs **YOLOv8 object detection**, and stores detections in the database.

# CCTV Server

A FastAPI-based backend for managing intersections, streets, CCTV cameras, regions, and detections.

---

## Tech Stack

* **FastAPI** – Web framework
* **SQLAlchemy** – ORM
* **MySQL** – Database
* **Pydantic** – Data validation
* **bcrypt** – Password hashing

---

## Setup

### 1. Environment Variables

Create a `.env` file:

```env
SUPER_KEY=your_super_secret_key
```

---

### 2. Database Configuration

Located in `common/database.py`:

```python
DATABASE_URL = "mysql+mysqlconnector://root:@localhost:3306/_20260301"
```

Update credentials as needed.

---

### 3. Run the Server

```bash
uvicorn server.main:app --reload
```

---

## Authentication

### Superuser Access

Used for `/users` endpoints.

```
Authorization: Bearer <SUPER_KEY>
```

---

### User Authentication

1. Login:

```
POST /login
```

2. Use returned token:

```
Authorization: Bearer <token>
```

---

## Data Model Overview

```
Intersection
 ├── Streets
 │     └── Regions
 │           ├── RegionPoints
 │           └── DetectionInRegion
 └── CCTVs
       └── Detections
```

---

## API Endpoints

---

# Users (Superuser Only)

## Create User

```
POST /users
```

**Body**

```json
{
  "username": "admin",
  "password": "password"
}
```

---

## Get All Users

```
GET /users
```

---

## Get User

```
GET /users/{user_id}
```

---

## Update User

```
PUT /users/{user_id}
```

---

## Delete User

```
DELETE /users/{user_id}
```

---

# Login

## Login

```
POST /login
```

**Response**

```json
{
  "token": "session_token"
}
```

---

## Logout

```
DELETE /login
```

---

# Intersections

## Create

```
POST /intersections
```

```json
{
  "name": "Intersection A",
  "latitude": 7.123,
  "longitude": 125.456
}
```

---

## Get All

```
GET /intersections
```

## Get One

```
GET /intersections/{id}
```

## Update

```
PUT /intersections/{id}
```

## Delete

```
DELETE /intersections/{id}
```

---

# Streets

## Create

```
POST /streets
```

```json
{
  "intersection_id": 1,
  "name": "Main Street"
}
```

---

## Get All

```
GET /streets
```

## Get One

```
GET /streets/{id}
```

## Update

```
PUT /streets/{id}
```

## Delete

```
DELETE /streets/{id}
```

---

# CCTVs

## Create

```
POST /cctvs
```

```json
{
  "intersection_id": 1,
  "name": "Camera 1",
  "rtsp_url": "rtsp://..."
}
```

---

## Get All

```
GET /cctvs
```

## Get One

```
GET /cctvs/{id}
```

## Update

```
PUT /cctvs/{id}
```

## Delete

```
DELETE /cctvs/{id}
```

---

# Regions

## Create

```
POST /regions
```

```json
{
  "cctv_id": 1,
  "street_id": 1,
  "region_points": [
    { "x": 10, "y": 20 },
    { "x": 30, "y": 40 }
  ]
}
```

---

## Get All

```
GET /regions
```

## Get One

```
GET /regions/{id}
```

## Update

```
PUT /regions/{id}
```

---

# Detections

## Get by CCTV

```
GET /detections/cctv/{cctv_id}
```

### Query Params

* `start_time` (optional)
* `end_time` (optional)

---

## Get by Region

```
GET /detections/region/{region_id}
```

---

## Logging

All write operations generate logs:

```
logs table:
- id
- message
- time
```

---

## Error Handling

| Status Code | Meaning      |
| ----------- | ------------ |
| 401         | Unauthorized |
| 404         | Not Found    |
| 400         | Bad Request  |
| 500         | Server Error |

---

## Notes for Developers

* All protected routes require **Bearer Token**
* Cascade deletes are enabled:

  * Deleting intersections removes streets, CCTVs, etc.
* Region updates **replace all points**
* Detection filtering supports time ranges
* Passwords are securely hashed using bcrypt

---

## Interactive Docs

After running:

* Swagger UI:
  `http://localhost:8000/docs`

* ReDoc:
  `http://localhost:8000/redoc`

---

# CCTV Worker

This project is a **computer vision pipeline** that uses **YOLOv8 object tracking** together with a **MySQL database (via SQLAlchemy)** to:

* Detect and track objects from CCTV streams
* Store detections in a database
* Map detections to predefined polygonal regions
* Record when tracked objects enter specific regions

---

## Features

* **Real-time object detection & tracking** using YOLOv8
* **RTSP / camera stream support**
* **Track persistence** across frames
* **Polygon-based region detection**
* **Relational database storage (MySQL)**
* **Automatic track pruning for stale objects**

---

## Project Structure

```
common/
├── database.py   # Database connection and session management
├── models.py     # SQLAlchemy ORM models

worker/
└── main.py       # Detection pipeline and processing logic
```

---

## Database Setup

### Configuration

Edit the database connection in:

```python
DATABASE_URL = "mysql+mysqlconnector://root:@localhost:3306/_20260301"
```

Make sure:

* MySQL is running
* Database exists (`_20260301`)
* Credentials are correct

---

### ORM Models Overview

#### Core Entities

* **User** – authentication and session tracking
* **Log** – system logs
* **Intersection** – physical locations
* **Street** – belongs to an intersection
* **CCTV** – camera devices linked to intersections

#### Detection Pipeline

* **Detection** – detected object (per track)
* **Region** – polygon areas tied to CCTV + street
* **RegionPoint** – vertices of a polygon
* **DetectionInRegion** – mapping of detection → region

---

### Relationships

* Intersection → Streets, CCTVs
* CCTV → Detections, Regions
* Region → RegionPoints, DetectionInRegion
* Detection → DetectionInRegion

---

## Installation

### 1. Install dependencies

```bash
pip install sqlalchemy mysql-connector-python ultralytics opencv-python
```

---

### 2. Download YOLO model

The system uses:

```
yolov8s.pt
```

It will auto-download via Ultralytics if not present.

---

## Running the Worker

```bash
python worker/main.py --cctv 1
```

### Arguments

| Argument  | Description                      |
| --------- | -------------------------------- |
| `--cctv`  | CCTV ID from the database        |
| `--debug` | Use local webcam instead of RTSP |

Example:

```bash
python worker/main.py --cctv 1 --debug
```

---

## How It Works

### 1. Initialization

* Loads CCTV config from DB
* Loads YOLOv8 model
* Loads regions (polygons) for the CCTV

---

### 2. Frame Processing Loop

For each frame:

1. Run YOLO tracking:

   ```python
   results = model.track(frame, persist=True)
   ```

2. Extract:

   * Bounding box
   * Class label
   * Track ID

3. Process detection:

   * Create DB record (if new track)
   * Compute bounding box center
   * Check region intersections

---

### 3. Region Detection

* Uses **ray casting algorithm** to check if a point lies inside a polygon:

```python
is_point_in_polygon(point, polygon)
```

---

### 4. Track State Management

Each tracked object keeps:

```python
TrackState:
- track_id
- cls_name
- db_detection_id
- regions_entered
- last_seen_ts
```

---

### 5. Pruning

Old tracks are removed periodically:

* Interval: `10 seconds`
* Max age: `30 seconds`

---

## Region Format

Regions are defined in the database:

* A region consists of multiple `(x, y)` points
* Points form a polygon
* Detection center must fall inside polygon to trigger

---

## Display

* Live annotated frames shown via OpenCV:

```python
cv2.imshow("frame", results[0].plot())
```

Press **`q`** to quit.

---

## Disclaimer

This documentation was generated by ChatGPT but the entire codebase was mostly written by hand.