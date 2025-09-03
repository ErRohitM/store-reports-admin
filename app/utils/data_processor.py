import os
import time
from datetime import datetime, timedelta, timezone, date
from multiprocessing import cpu_count, Pool
from typing import Any

import pandas as pd
from pandas import DataFrame
from tortoise.expressions import Q

from app.db_conn.redis_confg import ReportStatus
from app.models.business_menu import StoreMenuHour
from app.models.stores import StorePolls, StoreTimeZone
from app.models.report import StoreReportsStatus, store_report_status
from app.utils.common import convert_to_business_timezone, strftime


class BusinessAnalyzer:
    def __init__(self, report_id):
        self.report_id = report_id
        # self.report_manager = report_manager


    # main function
    async def main(self):
        """
        Main report generation method with Redis status updates
        :return:
        """
        try:
            from app.routes.report import report_manager

            # Update status to processing
            start_time = time.perf_counter()
            await report_manager.update_report_status(
                self.report_id,
                ReportStatus.PROCESSING,
                progress=0,
                message="Starting report generation"
            )

            report_df = pd.DataFrame()
            for window, day_counter in {'last_hour': 1, 'last_day': 1, 'last_week': 6}.items():
                # start_time = time.perf_counter()
                df_polls, df_business_hours, df_timezones = await self.preprocess_model_data(window)
                end_time = time.perf_counter()
                elapsed_time = end_time - start_time
                # progress status update, Redis: Processing
                await report_manager.update_report_status(
                    self.report_id, ReportStatus.PROCESSING, elapsed_time, "Processing time windows"
                )

                for _ in range(day_counter):
                    num_processes = cpu_count()  # Number of CPU cores available
                    if not df_polls.empty:
                        store_ids = df_polls['store_id'].unique()

                        with Pool(processes=num_processes) as pool:
                            results = pool.starmap(self.process_calculation_data,
                                                   [(store_id, df_polls, df_business_hours, window) for store_id in
                                                    store_ids])

                            end_time = time.perf_counter()
                            elapsed_time = end_time - start_time
                            # progress status update, Redis: Processing
                            await report_manager.update_report_status(
                                self.report_id, ReportStatus.PROCESSING, elapsed_time, "Processing time windows"
                            )

                        # Update the report dataframe from the results
                        report_df = pd.concat([report_df, pd.DataFrame(results)], ignore_index=True)
                    else:
                        continue
            # Store completed report
            await report_manager.store_report_data(self.report_id, self.report_id)

            if not os.path.exists('report_data'):
                os.makedirs('report_data')

            # finally
            # Save the report to a CSV file
            # in 3 tine window sizes
            report_file_path = f"report_data/report_{self.report_id}.csv"
            report_df.to_csv(report_file_path, index=False)

            end_time = time.perf_counter()
            elapsed_time = end_time - start_time
            await report_manager.update_report_status(
                self.report_id,
                ReportStatus.COMPLETED,
                progress=elapsed_time,
                message="Report generation completed"
            )

            # Update the report status to complete
            # filter existing report
            # if exist change status save
            # else: create new
            report_inst = await StoreReportsStatus.filter(report_id=self.report_id).exists()
            if not report_inst:
                report_data = store_report_status(
                    report_id=self.report_id,
                    report_status=True
                )
                await StoreReportsStatus.create(**report_data.dict())
            else:
                store_report_status.status = True
        except Exception as e:
            # Handle errors
            await report_manager.update_report_status(
                self.report_id,
                ReportStatus.FAILED,
                message=f"Report generation failed: {str(e)}"
            )
            # Log error details
            print(f"Report {self.report_id} failed: {str(e)}")

    async def preprocess_model_data(self, report_window) -> tuple[DataFrame, DataFrame | Any, DataFrame]:
        # cleaned filter for each time windows
        # polls and business hours
        # time window in UTC
        now_utc = datetime.now(timezone.utc)  # Current datetime UTC

        if report_window == 'last_hour':
            start_utc, stop_utc = (now_utc - timedelta(hours=1)), now_utc
            days = start_utc.weekday() or stop_utc.weekday()
        elif report_window == 'last_day':
            start_utc, stop_utc = ((now_utc - timedelta(days=1)), (now_utc - timedelta(days=1))
                                   .replace(hour=23, minute=59, second=59, microsecond=999999))
            days = start_utc.weekday() or stop_utc.weekday()
        else:
            # Calculate start of current week in UTC
            start_of_current_week_utc = now_utc - timedelta(days=now_utc.isoweekday() - 1)
            start_of_current_week_utc = start_of_current_week_utc.replace(hour=0, minute=0, second=0, microsecond=0)

            # Calculate start, end of last week in UTC
            start_of_last_week_utc = start_of_current_week_utc - timedelta(weeks=1)
            # add 6 more days to start of last week utc
            end_of_last_week_utc = start_of_last_week_utc + timedelta(days=6)
            end_of_last_week_utc = end_of_last_week_utc.replace(hour=23, minute=59, second=59, microsecond=999999)
            start_utc, stop_utc = start_of_last_week_utc, end_of_last_week_utc
            days = [7]

        # Fetch data from the app models
        df_store_data = await (StorePolls.all()
                               .filter(Q(timestamp_utc__gte=start_utc) &
                                       Q(timestamp_utc__lte=stop_utc))
                               .values("store_id", "timestamp_utc", "status"))

        day_lookup = [days] if isinstance(days, int) else list(range(7))
        df_business_hours_data = await (StoreMenuHour.all()
                                        .filter(day_of_week__in=day_lookup)
                                        .values("store_id", "day_of_week", "start_time_local",
                                                "end_time_local"))
        df_timezones_data = await  StoreTimeZone.all().values("store_id", "timezone_str")

        # Convert to pandas DataFrames
        df_status = pd.DataFrame(df_store_data)
        df_business_hours = pd.DataFrame(df_business_hours_data)
        df_timezones = pd.DataFrame(df_timezones_data)

        if not df_timezones.empty:
            # Filter out rows with missing store_id in df_timezones
            if not df_business_hours.empty:
                df_business_hours = df_business_hours[df_business_hours['store_id'].isin(df_timezones['store_id'])]
                # df_business_hours = sorted(df_business_hours['store_id'].unique())
                # df_business_hours = pd.DataFrame({'store_id': df_business_hours})

            # Convert timestamps into business timezone datetime objects
            if not df_status.empty:
                df_status['timestamp_local'] = df_status.apply(convert_to_business_timezone, args=(df_timezones,),
                                                               axis=1)
                df_status = df_status.sort_values(by='timestamp_local', ascending=False)

        return df_status, df_business_hours, df_timezones

    def process_calculation_data(self, store_id, df_polls, df_business_hours, reporting_window):
        df_store_polls = df_polls[df_polls['store_id'] == store_id]
        df_store_hours = df_business_hours[df_business_hours['store_id'] == store_id]

        if df_store_hours.empty:
            return {
                'store_id': store_id,
                **{f'{metric}_{window}': 0 for metric in ['uptime', 'downtime'] for window in
                   ['last_hour', 'last_day', 'last_week']}
            }

        class GetTimeWindows:
            def __init__(self, df_store_hour):
                # start window time from store hours
                # start time: min (start time local for each day)
                self.start_window_time = df_store_hour['start_time_local'].min()

                # stop window time from store hours
                # stop time: max(stop time local for each day)
                self.stop_window_time = df_store_hour['end_time_local'].max()

        get_time_windows = GetTimeWindows(df_store_hours)

        start_window_time = get_time_windows.start_window_time
        stop_window_time = get_time_windows.stop_window_time

        intervals = []
        prev_time = strftime(start_window_time)
        prev_status = False  # inactive

        for _, row in df_store_polls.iterrows():
            current_time = datetime.fromisoformat(row['timestamp_local'])
            t_as_datetime = datetime.combine(current_time.date(), prev_time)
            duration = ((current_time - t_as_datetime).total_seconds() / 60)  # in minutes
            intervals.append((duration, prev_status))
            prev_time = current_time.time()
            prev_status = row['status']

        stop_window = strftime(stop_window_time)
        # t_as_datetime = datetime.combine(prev_time.date(), stop_window)
        if prev_time < stop_window:
            prev_time = datetime.combine(date.min, prev_time)
            stop_window = datetime.combine(date.min, stop_window)
            duration = (stop_window - prev_time).total_seconds() / 60
            intervals.append((duration, prev_status))

        uptime = round(sum(d / 60 for d, s in intervals if s), 2) if (
                reporting_window in ['last_day', 'last_week']
        ) else round(sum(d for d, s in intervals if s), 2)

        downtime = round(sum(d / 60 for d, s in intervals if not s), 2) if (
                reporting_window in ['last_day', 'last_week']
        ) else round(sum(d for d, s in intervals if not s), 2)

        # return time window uptime, downtime
        return {
            'store_id': store_id,
            f"uptime_{reporting_window}": f"{uptime}",
            f"downtime_{reporting_window}": f"{downtime}"
        }
