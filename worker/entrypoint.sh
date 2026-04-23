#!/bin/bash
set -e

TRT_CACHE="${TRT_CACHE_DIR:-/app/trt_cache}"
ENGINE="${TRT_CACHE}/eyegila_v3.engine"

mkdir -p "$TRT_CACHE"
LOCKFILE="${TRT_CACHE}/export.lock"

(
  flock -x 200
  if [ ! -f "$ENGINE" ]; then
    echo "[entrypoint] TensorRT FP16 engine not found — exporting (first run, ~5-15 min)..."
    python - <<'PYEOF'
import os, shutil
from ultralytics import YOLO

cache = os.environ.get("TRT_CACHE_DIR", "/app/trt_cache")
dst = os.path.join(cache, "eyegila_v3.engine")
model = YOLO("/app/eyegila_v3.pt")
batch = int(os.environ.get("CAMERAS_PER_WORKER", "16"))
exported = model.export(format="engine", half=True, device=0, imgsz=480, dynamic=True, batch=batch)
shutil.move(str(exported), dst)
print(f"[entrypoint] engine saved to {dst}")
PYEOF
    echo "[entrypoint] Export complete."
  else
    echo "[entrypoint] TensorRT engine found at $ENGINE"
  fi
) 200>"$LOCKFILE"

exec python -m worker.main "$@"
