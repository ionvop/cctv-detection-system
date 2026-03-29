from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base


class Intersection(Base):
    __tablename__ = "intersections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    intersection_id = Column(Integer, ForeignKey("intersections.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    cctvs = relationship("CCTV", back_populates="intersection")
    summaries = relationship("AggregationSummary", back_populates="intersection")


class CCTV(Base):
    __tablename__ = "cctvs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    stream_key = Column(String(255), nullable=False)
    status = Column(String(50), default="offline", nullable=False)
    intersection_id = Column(Integer, ForeignKey("intersections.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    intersection = relationship("Intersection", back_populates="cctvs")
    regions = relationship("Region", back_populates="cctv", cascade="all, delete")
    detections = relationship("Detection", back_populates="cctv", cascade="all, delete")
    heartbeat = relationship("WorkerHeartbeat", back_populates="cctv", uselist=False, cascade="all, delete")


class Region(Base):
    __tablename__ = "regions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cctv_id = Column(Integer, ForeignKey("cctvs.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    x1 = Column(Float, nullable=False)
    y1 = Column(Float, nullable=False)
    x2 = Column(Float, nullable=False)
    y2 = Column(Float, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    cctv = relationship("CCTV", back_populates="regions")
    detections = relationship("Detection", back_populates="region")


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cctv_id = Column(Integer, ForeignKey("cctvs.id", ondelete="CASCADE"), nullable=False, unique=True)
    worker_pid = Column(Integer, nullable=False)
    last_seen = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    claimed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(String(50), default="running", nullable=False)
    frames_per_second = Column(Float, nullable=True)

    cctv = relationship("CCTV", back_populates="heartbeat")


class Detection(Base):
    __tablename__ = "detections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cctv_id = Column(Integer, ForeignKey("cctvs.id", ondelete="CASCADE"), nullable=False)
    intersection_id = Column(Integer, ForeignKey("intersections.id", ondelete="SET NULL"), nullable=True)
    region_id = Column(Integer, ForeignKey("regions.id", ondelete="SET NULL"), nullable=True)
    detected_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    object_type = Column(String(50), nullable=False)
    confidence = Column(Float, nullable=False)
    x1 = Column(Float, nullable=False)
    y1 = Column(Float, nullable=False)
    x2 = Column(Float, nullable=False)
    y2 = Column(Float, nullable=False)

    cctv = relationship("CCTV", back_populates="detections")
    intersection = relationship("Intersection")
    region = relationship("Region", back_populates="detections")


class AggregationSummary(Base):
    __tablename__ = "aggregation_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    intersection_id = Column(Integer, ForeignKey("intersections.id", ondelete="CASCADE"), nullable=False)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_size = Column(Integer, nullable=False)
    car_count = Column(Integer, default=0, nullable=False)
    truck_count = Column(Integer, default=0, nullable=False)
    pedestrian_count = Column(Integer, default=0, nullable=False)
    motorcycle_count = Column(Integer, default=0, nullable=False)
    tricycle_count = Column(Integer, default=0, nullable=False)
    pedicab_count = Column(Integer, default=0, nullable=False)
    total_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    intersection = relationship("Intersection", back_populates="summaries")