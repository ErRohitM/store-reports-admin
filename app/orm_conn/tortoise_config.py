from app.db_conn.db_config import DATABASE_URL

TORTOISE_ORM = {
    "connections": {"default": DATABASE_URL},
    "apps": {
        "pnwapi": {
            "models": [
                "app.models.stores",
                "app.models.business_menu",
                "app.models.report",
                "aerich.models"
            ],
            "default_connection": "default",
        }
    }
}
