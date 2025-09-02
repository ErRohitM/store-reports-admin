from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "store_status" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "store_id" UUID NOT NULL,
    "timestamp_utc" TIMESTAMPTZ NOT NULL,
    "status" BOOL NOT NULL DEFAULT False
);
COMMENT ON TABLE "store_status" IS 'Roughly Every Hour Polls Data';
CREATE TABLE IF NOT EXISTS "timezone_store" (
    "store_id" UUID NOT NULL PRIMARY KEY,
    "timezone_str" VARCHAR(100) NOT NULL DEFAULT 'America/Chicago'
);
COMMENT ON TABLE "timezone_store" IS 'Timezone for the stores';
CREATE TABLE IF NOT EXISTS "store_menu_hour" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "store_id" UUID NOT NULL,
    "created_at" TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    "day_of_week" INT NOT NULL,
    "start_time_local" VARCHAR(125) NOT NULL,
    "end_time_local" VARCHAR(125) NOT NULL,
    CONSTRAINT "uid_store_menu__store_i_121a6f" UNIQUE ("store_id", "day_of_week", "start_time_local", "end_time_local")
);
COMMENT ON TABLE "store_menu_hour" IS 'business hours of all the stores';
CREATE TABLE IF NOT EXISTS "storereportsstatus" (
    "report_id" UUID NOT NULL PRIMARY KEY,
    "status" BOOL NOT NULL DEFAULT False
);
COMMENT ON TABLE "storereportsstatus" IS 'Report status model';
CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """
