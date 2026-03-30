from pydantic import BaseModel, ConfigDict
from datetime import datetime
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
    time: datetime
    model_config = ConfigDict(from_attributes=True)


class IntersectionBase(BaseModel):
    name: str


class IntersectionCreate(IntersectionBase):
    pass


class IntersectionUpdate(BaseModel):
    name: Optional[str] = None


class IntersectionResponse(IntersectionBase):
    id: int
    time: datetime
    model_config = ConfigDict(from_attributes=True)