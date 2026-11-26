from pydantic import BaseModel, EmailStr, Field
from typing import Literal

class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
class LoginIn(BaseModel):
    email: EmailStr
    password: str
class UserOut(BaseModel):
    id: int; name: str; email: str; role: str
    model_config = {"from_attributes": True}
class BuildingIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    building_type: str = "Academic"
class AreaIn(BaseModel):
    building_id: int
    name: str = Field(min_length=1, max_length=120)
    area_type: str
    room_number: str | None = None
class ReportIn(BaseModel):
    area_id: int
    description: str = Field(min_length=5, max_length=3000)
class StatusIn(BaseModel):
    status: Literal["In Progress", "Resolved", "Unable to Resolve"]
    remarks: str | None = Field(default=None, max_length=2000)
class StaffIn(BaseModel):
    name: str
    email: EmailStr
    password: str = Field(min_length=8)
class AssignmentIn(BaseModel):
    area_id: int
    staff_id: int
