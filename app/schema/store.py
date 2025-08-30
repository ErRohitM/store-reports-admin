import uuid
from datetime import datetime
from pydantic import BaseModel, Field

class StorePollingCreate(BaseModel):
    """
    polls every store roughly every hour
    """
    store_id: uuid.UUID = Field(default_factory=uuid.uuid4) # Generates a new UUID on creation
    timestamp_utc: datetime
    status: bool

    # allow ORM
    class Config:
        from_attributes = True

class StoreTimeZoneCreate(BaseModel):
    """
    create store time zone
    """
    store_id: uuid.UUID = Field(default_factory=uuid.uuid4) # Generates a new UUID on creation
    timezone_str: str

    # allow ORM
    class Config:
        from_attributes = True
