from tortoise import fields, models
from tortoise.contrib.pydantic import pydantic_model_creator
from tortoise.validators import MinValueValidator, MaxValueValidator

class AbstractStoreModel(models.Model):
    """
    base store info
    """
    store_id = fields.UUIDField(null=False)
    # created timestamp
    created_at = fields.DatetimeField(null=True, auto_now_add=True)
    # modified timestamp is not necessary

    class Meta:
        abstract = True

class StoreMenuHour(AbstractStoreModel):
    """
    business hours of all the stores
    inherits Abstract Store id and created at
    """
    day_of_week = fields.IntField(
        validators=[
            MinValueValidator(0),
            MaxValueValidator(6)
        ]
    ) # days of the week [0-6]
    start_time_local = fields.CharField(max_length=125, null=False) # store as char
    end_time_local = fields.CharField(max_length=125, null=False)

    class Meta:
        table = "store_menu_hour"
        unique_together = ("store_id", "day_of_week", "start_time_local", "end_time_local")

# create StoreMenuHour Migrations
Store_menu_time_pydantic = pydantic_model_creator(StoreMenuHour, name="Store Menu Hour")