from models import Base, CCTV, Detection, Coord
from database import SessionLocal, engine
from ultralytics import YOLO
import time
import cv2


CCTV_ID = 2


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    model = YOLO("yolov8s.pt")
    cap = cv2.VideoCapture(2)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    try:
        while True:
            coords = get_coords(cap, model)

            if len(coords) > 0:
                detection = Detection(cctv_id=CCTV_ID)
                
                for coord in coords:
                    detection.coords.append(Coord(x=coord["x"], y=coord["y"]))

                db.add(detection)
                db.commit()
                print(f"{len(coords)} detection{'' if len(coords) == 1 else 's'} added to CCTV {CCTV_ID}")
    except KeyboardInterrupt:
        print("Exiting...")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        db.close()


def get_coords(cap: cv2.VideoCapture, model: YOLO, duration: float = 1.0) -> list:
    if not cap.isOpened():
        raise RuntimeError("Could not open webcam.")

    start_time = time.time()
    max_centers = []
    max_count = 0

    while time.time() - start_time < duration:
        ret, frame = cap.read()
        print("Reading frame...", int((time.time() - start_time) * 1000))

        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0) # if cap is retrieving from a video file instead of webcam
            continue

        height, width = frame.shape[:2]
        results = model(frame, verbose=False)
        annotated_frame = results[0].plot()
        cv2.imshow("Detections", annotated_frame)
        cv2.waitKey(1)
        result = results[0]

        if result.boxes is None or len(result.boxes) == 0:
            continue

        current_boxes = result.boxes.xyxy.cpu().tolist()
        current_count = len(current_boxes)

        if current_count > max_count:
            max_count = current_count
            centers = []

            for x1, y1, x2, y2 in current_boxes:
                center_x = ((x1 + x2) / 2) / width
                center_y = ((y1 + y2) / 2) / height

                centers.append({
                    "x": max(0.0, min(1.0, center_x)),
                    "y": max(0.0, min(1.0, center_y)),
                })

            max_centers = centers

    return max_centers


if __name__ == "__main__":
    main()