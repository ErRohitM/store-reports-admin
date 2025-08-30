import uuid
from datetime import time

from pydantic import BaseModel, Field


class StoreBusinessHourCreate(BaseModel):
    """
    create StoreMenuHour
    """
    store_id: uuid.UUID = Field(default_factory=uuid.uuid4)  # Generates a new UUID, new creation
    day_of_week: int
    start_time_local: time
    end_time_local: time

    # allow ORM
    class Config:
        from_attributes = True