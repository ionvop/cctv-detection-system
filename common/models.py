from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base
import time


def unix_epoch():
    return int(time.time())


class Street(Base):
    __tablename__ = "streets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    time = Column(Integer, default=unix_epoch, nullable=False)

    cctvs = relationship("CCTV", back_populates="street", cascade="all, delete")


class CCTV(Base):
    __tablename__ = "cctvs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    street_id = Column(Integer, ForeignKey("streets.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    time = Column(Integer, default=unix_epoch, nullable=False)

    street = relationship("Street", back_populates="cctvs")
    detections = relationship("Detection", back_populates="cctv", cascade="all, delete")


class Detection(Base):
    __tablename__ = "detections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    cctv_id = Column(Integer, ForeignKey("cctvs.id", ondelete="CASCADE"), nullable=False)

    x = Column(Float, nullable=False)
    y = Column(Float, nullable=False)

    time = Column(Integer, default=unix_epoch, nullable=False)

    cctv = relationship("CCTV", back_populates="detections")