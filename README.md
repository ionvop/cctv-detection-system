# CCTV Detection System

TODO: Update this `README.md` file to reflect the current state of the project.

A simple CCTV detection system built with **FastAPI**, **MySQL**, and **YOLOv8**.

The project consists of two components:

1. **Server** – REST API for managing CCTV cameras and retrieving detection data.
2. **Worker** – A computer vision worker that reads video from a webcam, runs **YOLOv8 object detection**, and stores detections in the database.

---

# Architecture

```

+-------------+        +-------------+        +-----------+
|   Webcam    | -----> |   Worker    | -----> |  MySQL DB |
| (OpenCV)    |        | YOLOv8      |        |           |
+-------------+        +-------------+        +-----------+
|
v
+-------------+
|   FastAPI   |
|    Server   |
+-------------+

```

### Components

#### Server
- Built with **FastAPI**
- Handles API requests
- Manages CCTV records
- Provides detection query endpoints

#### Worker
- Uses **OpenCV** for video capture
- Uses **YOLOv8 (Ultralytics)** for object detection
- Saves detection coordinates to the database

---

# Database Schema

### `cctvs`
| Field | Type | Description |
|------|------|-------------|
| id | int | Primary key |
| name | string | CCTV name |
| time | int | Unix timestamp |

### `detections`
| Field | Type | Description |
|------|------|-------------|
| id | int | Primary key |
| cctv_id | int | CCTV reference |
| time | int | Detection timestamp |

### `coords`
| Field | Type | Description |
|------|------|-------------|
| id | int | Primary key |
| detection_id | int | Detection reference |
| x | float | Normalized X coordinate (0–1) |
| y | float | Normalized Y coordinate (0–1) |
| time | int | Timestamp |

Coordinates are normalized relative to frame width/height.

---

# Project Structure

```

project/
│
├── server/
│   ├── main.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── requirements.txt
│   └── routers/
│       ├── cctv.py
│       └── detections.py
│
└── worker/
    ├── main.py
    ├── database.py
    ├── models.py
    └── requirements.txt

````

---

# Installation

## 1. Clone the Repository

```bash
git clone https://github.com/ionvop/cctv-detection-system.git
cd cctv-detection-system
````

---

# Database Setup

Create a MySQL database:

```sql
CREATE DATABASE your_database;
```

Default connection string:

```
mysql+mysqlconnector://root:@localhost:3306/your_database
```

Modify `DATABASE_URL` in:

```
server/database.py
worker/database.py
```

if needed.

---

# Server Setup

## Install dependencies

```bash
cd server
pip install -r requirements.txt
```

## Run the server

```bash
fastapi dev main.py
```

or

```bash
uvicorn main:app --reload
```

Server will start at:

```
http://localhost:8000
```

Interactive API docs:

```
http://localhost:8000/docs
```

---

# Worker Setup

## Install dependencies

```bash
cd worker
pip install -r requirements.txt
```

YOLOv8 weights (`yolov8s.pt`) is not included in the repository.

## Run the worker

```bash
python main.py
```

The worker will:

1. Open your webcam
2. Detect objects using YOLOv8
3. Track the **maximum number of detections within 1 second**
4. Save normalized coordinates to the database

---

# API Endpoints

## CCTV

### Create CCTV

```
POST /cctvs
```

Body:

```json
{
  "name": "Entrance Camera"
}
```

---

### Get All CCTVs

```
GET /cctvs
```

---

### Get CCTV by ID

```
GET /cctvs/{cctv_id}
```

---

### Update CCTV

```
PUT /cctvs/{cctv_id}
```

Body:

```json
{
  "name": "New Name"
}
```

---

### Delete CCTV

```
DELETE /cctvs/{cctv_id}
```

---

## Detections

### Get Detections

```
GET /cctvs/{cctv_id}/detections
```

### Query Parameters

| Parameter      | Type  | Description          |
| -------------- | ----- | -------------------- |
| start_time     | int   | Unix start timestamp |
| end_time       | int   | Unix end timestamp   |
| region_start_x | float | Region filter (0–1)  |
| region_start_y | float | Region filter (0–1)  |
| region_end_x   | float | Region filter (0–1)  |
| region_end_y   | float | Region filter (0–1)  |

Example:

```
GET /cctvs/1/detections?start_time=1700000000&end_time=1700000600
```

Example with region filter:

```
GET /cctvs/1/detections?start_time=1700000000&end_time=1700000600&region_start_x=0.2&region_start_y=0.2&region_end_x=0.6&region_end_y=0.6
```

---

# Detection Logic

The worker:

1. Captures frames from webcam
2. Runs YOLOv8 detection
3. Tracks the frame with the **maximum number of detected objects within 1 second**
4. Saves center coordinates of bounding boxes

Coordinates are stored as normalized values:

```
x = center_x / frame_width
y = center_y / frame_height
```

---

# Example Detection Response

```json
[
  {
    "id": 12,
    "time": 1700001234,
    "coords": [
      { "x": 0.42, "y": 0.61 },
      { "x": 0.55, "y": 0.48 }
    ]
  }
]
```

---

# Technologies Used

* FastAPI
* SQLAlchemy
* MySQL
* OpenCV
* YOLOv8 (Ultralytics)
* Pydantic

---

## Disclaimer

This documentation was generated by ChatGPT but the entire codebase was mostly written by hand.