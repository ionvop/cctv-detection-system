from pydantic import BaseModel, ConfigDict
from typing import Optional


class UserBase(BaseModel):
    username: str
    password: str


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    password: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    username: str
    time: int
    model_config = ConfigDict(from_attributes=True)


class IntersectionBase(BaseModel):
    name: str


class IntersectionCreate(IntersectionBase):
    pass


class IntersectionUpdate(BaseModel):
    name: Optional[str] = None


class IntersectionResponse(IntersectionBase):
    id: int
    time: int
    model_config = ConfigDict(from_attributes=True)


class CCTVBase(BaseModel):
    name: str


class CCTVCreate(CCTVBase):
    pass


class CCTVUpdate(BaseModel):
    name: Optional[str] = None


class CCTVResponse(CCTVBase):
    id: int
    time: int
    model_config = ConfigDict(from_attributes=True)


class CoordResponse(BaseModel):
    x: float
    y: float
    model_config = ConfigDict(from_attributes=True)


class DetectionResponse(BaseModel):
    id: int
    time: int
    coords: list[CoordResponse]
    model_config = ConfigDict(from_attributes=True)