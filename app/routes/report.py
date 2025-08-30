
from fastapi import APIRouter, Request, HTTPException

from app.schema.store import StoreTimeZoneCreate
from app.utils.report_generator import StoreReportTimeWindow, StoreBusinessAnalyzer

router = APIRouter(prefix="/reports", tags=["utils"])

@router.get("/trigger_report")
async def generate_reports(request: Request):
    """
    Generate Reports:
    Process store time window start, end in local,
    Extrapolate uptime and downtime:
        filter business hours: processed local time windows:
        filter polls: processed local start, end, store_id
        interpolation missing business hour windows
        none: open 24*7 / full_day_window
        calculate uptime & downtimes for each time windows
    generate report:
    :param request:
    :return: report_id
    """
    store_ids = ["1632a271-fdc4-45ad-8dee-4383d49cde6b", "0a1d42a2-f6ad-4c6b-9617-375126714502", "8489c804-fdc9-4814-ac40-2094986632fe"]
    uptime_downtime_windows = []
    for store_id in store_ids:
        for window in ["last_hour", "last_day", "last_week"]:
            # get start, stop local times
            # in business window
            report_time_windows = StoreReportTimeWindow()
            reports_time_windows = await report_time_windows.main(store_id, window)

            # extrapolate uptime and downtime
            extrapolate_report_windows = StoreBusinessAnalyzer()
            uptime_downtime_window = await extrapolate_report_windows.main(store_id, reports_time_windows, window)
            uptime_downtime_windows.append(f"{store_id} {uptime_downtime_window}")

    return uptime_downtime_windows