
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks

from app.utils.common import generate_unique_report_id
from app.models.report import StoreReportsStatus, store_report_status
from app.utils.data_processor import BusinessAnalyzer

router = APIRouter(prefix="/reports", tags=["utils"])

@router.get("/trigger_report", tags=["Reports"], response_model=dict)
async def generate_reports(background_tasks: BackgroundTasks):
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
    # Generate a unique report_id
    report_id = await generate_unique_report_id()
    # Temp: Insert the report_id into the database with status=False
    report_data = store_report_status(
        report_id=report_id,
        status=False
    )
    await StoreReportsStatus.create(**report_data.dict())

    # Run the compute_and_save_report function in the background with the generated report_id
    analyzer = BusinessAnalyzer(report_id=report_id)
    background_tasks.add_task(analyzer.main)

    return {"report_id": report_id}
