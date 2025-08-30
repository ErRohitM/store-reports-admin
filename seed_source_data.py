import os
import time
from datetime import time
from uuid import UUID

from tortoise import Tortoise, run_async
from app.db_conn.db_config import DATABASE_URL
import pandas as pd

from app.models.stores import StorePolls, StoreTimeZone
from app.models.business_menu import StoreMenuHour
from app.schema.store import StorePollingCreate, StoreTimeZoneCreate
from app.schema.menu_hours import StoreBusinessHourCreate

# initialize db
async def init_db_stores():
    await Tortoise.init(
        db_url=DATABASE_URL,
        modules={"models": ["app.models.stores"]},
    )
    await Tortoise.generate_schemas()

# seed into StorePolls
async def seed_store_polls(file_path: str):
    menu_df = pd.read_csv(file_path, usecols=["store_id", "timestamp_utc", "status"])
    # async with Tortoise.get_connection("default")._in_transaction() as conn:
    for _, row in menu_df.iterrows():
        try:
            # Validate and parse with Pydantic
            poll_data = StorePollingCreate(
                store_id=UUID(row["store_id"]),
                timestamp_utc=row["timestamp_utc"].replace(" UTC", ""),
                status=True if str(row["status"]).lower() == "active" else False
            )
            # Insert record
            await StorePolls.create(**poll_data.dict())
        except Exception as e:
            print(f"Skipping row due to error: {row.to_dict()} -> {e}")


# seed into StoreMenuHour
async def seed_store_time_zone(file_path: str):
    timezone_df = pd.read_csv(file_path, usecols=["store_id", "timezone_str"])
    for _, row in timezone_df.iterrows():
        try:
            # Validate and parse with Pydantic
            timezone_data = StoreTimeZoneCreate(
                store_id=UUID(row["store_id"]),
                timezone_str=row["timezone_str"]
            )
            # Insert record
            await StoreTimeZone.create(**timezone_data.dict())
        except Exception as e:
            print(f"Skipping row due to error: {row.to_dict()} -> {e}")

# initialize db
async def init_db_menu_hours():
    await Tortoise.init(
        db_url=DATABASE_URL,
        modules={"models": ["app.models.business_menu"]},
    )
    await Tortoise.generate_schemas()

# seed into StoreMenuHour
async def seed_store_business_hours(file_path: str):
    menu_df = pd.read_csv(file_path, usecols=["store_id", "dayOfWeek", "start_time_local", "end_time_local"])
    # menu_df_filtered = menu_df.drop_duplicates(subset=['store_id', 'dayOfWeek', 'start_time_local', 'end_time_local'])
    menu_df_filtered = menu_df.groupby(['store_id', 'dayOfWeek', 'start_time_local', 'end_time_local']).size().reset_index(
        name='count')

    for _, row in menu_df_filtered.iterrows():
        try:
            # Validate and parse with Pydantic
            menu_hour_data = StoreBusinessHourCreate(
                store_id=UUID(row["store_id"]),
                day_of_week=row["dayOfWeek"],
                start_time_local=row["start_time_local"],
                end_time_local=row["end_time_local"]
            )
            # Insert record
            await StoreMenuHour.create(**menu_hour_data.dict())
        except Exception as e:
            print(f"Skipping row due to error: {row.to_dict()} -> {e}")

# read source dir, fetch csv files
folder_path = "store-monitoring-data"
file_names = os.listdir(folder_path)

async def main():
    # await init_db_menu_hours()
    # try:
    #     await seed_store_business_hours(os.path.join(folder_path, file_names[0]))
    # finally:
    #     await Tortoise.close_connections()

    await  init_db_stores()
    try:
        await seed_store_polls(os.path.join(folder_path, file_names[1]))
        # await seed_store_time_zone(os.path.join(folder_path, file_names[2]))
    finally:
        await Tortoise.close_connections()

if __name__ == "__main__":
    run_async(main())
