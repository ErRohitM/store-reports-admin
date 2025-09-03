
from fastapi import APIRouter, Request, HTTPException, BackgroundTasks

from app.db_conn.redis_confg import redis_client, ReportStatus
from app.utils.common import generate_unique_report_id
from app.models.report import StoreReportsStatus, store_report_status
from app.utils.data_processor import BusinessAnalyzer
from app.utils.report_management import ReportManager

router = APIRouter(prefix="/reports", tags=["Reports"])

# Initialize report manager
report_manager = ReportManager(redis_client)

@router.get("/trigger_report", response_model=dict)
async def generate_reports(background_tasks: BackgroundTasks):
    try:
        """
        Trigger report generation and return report_id immediately
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

        # Initialize report task in Redis
        await report_manager.create_report_task(report_id)

        # Store in database for persistence (optional)
        report_data = store_report_status(report_id=report_id, status=False)
        await StoreReportsStatus.create(**report_data.dict())

        # Start background task
        analyzer = BusinessAnalyzer(report_id=report_id)
        background_tasks.add_task(analyzer.main)

        return {
            "report_id": str(report_id),
            "status": "pending",
            "message": "Report generation started. Use /report_status/{report_id} to check progress."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start report generation: {str(e)}")


@router.get("/get_report/{report_id}", tags=["Reports"], response_model=dict)
async def get_report_status(report_id: str):
    """
    Get Report Id,
    current status,
     Logs,
     csv file (downloadable) -> if complete
     data availability status
     of report generation
    """
    status_info = await report_manager.get_report_status(report_id)

    if not status_info:
        raise HTTPException(status_code=404, detail="Report not found")

    response = {
        "report_id": report_id,
        "status": status_info["status"],
        "progress": status_info.get("progress", 0),
        "message": status_info.get("message", ""),
        "created_at": status_info.get("created_at"),
        "updated_at": status_info.get("updated_at")
    }

    # If completed, include download link
    if status_info["status"] == ReportStatus.COMPLETED:
        response["download_url"] = f"/report_data/report_{report_id}.csv"
        response["data_available"] = True

    # Add estimated completion time for processing reports
    elif status_info["status"] == ReportStatus.PROCESSING:
        progress = status_info.get("progress", 0)
        if progress > 0:
            # Simple ETA calculation (you can make this more sophisticated)
            estimated_total_time = 300  # 5 minutes average
            elapsed_ratio = progress / 100
            remaining_time = estimated_total_time * (1 - elapsed_ratio)
            response["estimated_completion_seconds"] = int(remaining_time)

    return response