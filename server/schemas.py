from pydantic import BaseModel
from typing import Optional


class CCTVBase(BaseModel):
    name: str


class CCTVCreate(CCTVBase):
    pass


class CCTVUpdate(BaseModel):
    name: Optional[str] = None


class CCTVResponse(CCTVBase):
    id: int
    time: int

    class Config:
        orm_mode = True


class CoordResponse(BaseModel):
    x: float
    y: float

    class Config:
        orm_mode = True


class DetectionResponse(BaseModel):
    id: int
    time: int
    coords: list[CoordResponse]

    class Config:
        orm_mode = True