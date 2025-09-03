import uuid
from ast import parse
from datetime import datetime

from pytz import timezone

from app.models.report import StoreReportsStatus

async def generate_unique_report_id():
    report_id = uuid.uuid4()
    # check if generating report is is already exist
    is_report_id = await StoreReportsStatus.get_or_none(report_id=report_id)
    if not is_report_id:
        return report_id

def convert_to_business_timezone(timestamp_dt_row, df_timezones):
    store_id = timestamp_dt_row['store_id']
    timezone_info = df_timezones.loc[df_timezones['store_id'] == store_id, 'timezone_str']
    if not timezone_info.empty:
        timestamp_utc = timestamp_dt_row['timestamp_utc']
        tz_str = timezone_info.values[0]
        tz_local = timezone(tz_str)
        dt_local = timestamp_utc.astimezone(tz_local)
        return dt_local.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-4]
    else:
        return None

def strftime(time_str: str) -> datetime.time:
    if isinstance(time_str, str):
        return datetime.strptime(time_str, "%H:%M:%S").time()
