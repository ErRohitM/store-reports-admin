from tortoise import fields, models
from tortoise.contrib.pydantic import pydantic_model_creator

class StoreReportsStatus(models.Model):
    """
    Report status model
    """
    report_id = fields.UUIDField(primary_key=True)
    status = fields.BooleanField(default=False)

"""
StoreReportsStatus pydantic model
"""
store_report_status = pydantic_model_creator(StoreReportsStatus, name='store_report_status')