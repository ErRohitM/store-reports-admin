from tortoise import fields, models
from tortoise.contrib.pydantic import pydantic_model_creator

class StorePolls(models.Model):
    """
    Roughly Every Hour Polls Data
    """
    store_id = fields.UUIDField(null=False, unique=False) #cannot be null, allow duplicates
    # timestamp in UTC
    timestamp_utc = fields.DatetimeField(null=False, auto_now=False, use_tz=True) #auto now is for csv data, can be changed True for other cases
    # status can be active OR inactive
    status = fields.BooleanField(default=False, null=False) # True => active, False => inactive

    class Meta:
        table = "store_status"

class StoreTimeZone(models.Model):
    """
    Timezone for the stores
    """
    store_id = fields.UUIDField(primary_key=True)
    timezone_str = fields.CharField(max_length=100, default="America/Chicago")

    class Meta:
        table = "timezone_store"


"""
create Store pydantic model
serialize StorePolls
"""
store_pydantic = pydantic_model_creator(StorePolls, name="StoreStatus")

"""
Store TimeZone pydantic model
serialize StoreTimeZone
"""
store_time_zone_pydantic = pydantic_model_creator(StoreTimeZone, name="TimeZoneStore")