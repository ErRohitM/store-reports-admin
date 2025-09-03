import redis
from enum import Enum

class ReportStatus(str, Enum):
    """
    Report Status enum
    """
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# Redis configuration
redis_client = redis.Redis(
    host='localhost',
    port=6379,
    db=0,
    decode_responses=True
)

# Redis key patterns
REPORT_STATUS_KEY = "report:status:{report_id}"
REPORT_DATA_KEY = "report:data:{report_id}"
REPORT_PROGRESS_KEY = "report:progress:{report_id}"