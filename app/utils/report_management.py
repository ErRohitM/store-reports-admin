import json
import uuid
from datetime import datetime
from typing import Optional

from app.db_conn.redis_confg import REPORT_STATUS_KEY, ReportStatus, REPORT_DATA_KEY


class ReportManager:
    def __init__(self, redis_client):
        self.redis = redis_client
        self.status_ttl = 86400  # 24 hours
        self.data_ttl = 604800  # 7 days

    def _serialize_data(self, data):
        """Custom serializer to handle UUIDs, Enums, and other non-JSON types"""
        if data is None:
            return "{}"

        def json_serializer(obj):
            # Handle UUID objects
            if isinstance(obj, uuid.UUID):
                return str(obj)

            # Handle datetime objects
            elif isinstance(obj, datetime):
                return obj.isoformat()

            # Handle Enum objects (like ReportStatus)
            elif hasattr(obj, 'value') and hasattr(obj, 'name'):
                return obj.value  # Return the enum's value ('pending', 'processing', etc.)

            # Handle other custom objects
            elif hasattr(obj, '__dict__'):
                return obj.__dict__

            raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

        try:
            result = json.dumps(data, default=json_serializer)
            return result
        except Exception as e:
            return json.dumps({"error": "serialization_failed", "data": str(data)})

    def _deserialize_data(self, json_str):
        """Custom deserializer"""
        return json.loads(json_str) if json_str else None

    async def create_report_task(self, report_id) -> dict:  # Accept any type
        """Initialize report task in Redis"""
        # Convert report_id to string if it's a UUID
        report_id_str = str(report_id) if isinstance(report_id, uuid.UUID) else report_id

        report_info = {
            "report_id": report_id_str,
            "status": ReportStatus.PENDING.value,
            "created_at": datetime.utcnow().isoformat(),
            "progress": 0,
            "message": "Report generation queued"
        }

        # Store in Redis with TTL
        key = REPORT_STATUS_KEY.format(report_id=report_id_str)
        value = json.dumps(report_info)
        self.redis.setex(
            key,
            self.status_ttl,
            value
        )

        return report_info

    async def update_report_status(self, report_id, status: ReportStatus,
                                   progress: int = None, message: str = None):
        """Update report status in Redis"""
        report_id_str = str(report_id) if isinstance(report_id, uuid.UUID) else report_id
        key = REPORT_STATUS_KEY.format(report_id=report_id_str)

        # Get existing data
        existing_data = self.redis.get(key)
        if existing_data:
            report_info = self._deserialize_data(existing_data)
            report_info["status"] = status
            report_info["updated_at"] = datetime.utcnow().isoformat()

            if progress is not None:
                report_info["progress"] = progress
            if message is not None:
                report_info["message"] = message


            value = json.dumps(report_info)
            self.redis.setex(key, self.status_ttl, value)

    async def store_report_data(self, report_id, data):
        """Store completed report data"""
        report_id_str = str(report_id) if isinstance(report_id, uuid.UUID) else report_id
        self.redis.setex(
            REPORT_DATA_KEY.format(report_id=report_id_str),
            self.data_ttl,
            self._serialize_data(data)
        )

    async def get_report_status(self, report_id) -> Optional[dict]:
        """Get report status from Redis"""
        report_id_str = str(report_id) if isinstance(report_id, uuid.UUID) else report_id
        key = REPORT_STATUS_KEY.format(report_id=report_id_str)
        data = self.redis.get(key)
        return self._deserialize_data(data)

    async def get_report_data(self, report_id) -> Optional[dict]:
        """Get completed report data"""
        report_id_str = str(report_id) if isinstance(report_id, uuid.UUID) else report_id
        key = REPORT_DATA_KEY.format(report_id=report_id_str)
        data = self.redis.get(key)
        return self._deserialize_data(data)