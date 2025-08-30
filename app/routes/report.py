
from fastapi import APIRouter, Request, HTTPException

from app.schema.store import StoreTimeZoneCreate
from app.utils.report_generator import StoreReportTimeWindow, StoreBusinessAnalyzer

router = APIRouter(prefix="/reports", tags=["utils"])

@router.get("/trigger_report")
async def generate_reports(request: Request):
    """
    Generate Reports:
    process store time window start, end in local
    extrapolate uptime and downtime
        filter business hours: processed local time windows:
            none: open 24*7 / full_day_window
        filter polls: processed local start, end, store_id
        interpolation missing business hour windows
        calculate uptime & downtimes for each time windows
    generate report:
    :param request:
    :return: report_id
    """
    store_id = "7a242d0e-309c-4915-9755-e9019d69108d"
    # get start, stop local times
    # in business window
    report_time_windows = StoreReportTimeWindow()
    get_local_time_windows_n_days = await report_time_windows.main(store_id)

    # extrapolate uptime and downtime
    extrapolate_report_windows = StoreBusinessAnalyzer()
    uptime_downtime_windows = await extrapolate_report_windows.main(store_id, get_local_time_windows_n_days)

    return uptime_downtime_windows