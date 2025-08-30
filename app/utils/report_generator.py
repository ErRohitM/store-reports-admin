import pandas as pd
from collections import defaultdict
from configparser import Interpolation
from datetime import datetime, timedelta, timezone, tzinfo
from typing import TypedDict, Dict, List, Optional

import pytz
from numpy.ma.core import floor, ceil
from tortoise.expressions import Q, Case, When, F

from app.models.business_menu import StoreMenuHour
from app.models.stores import StoreTimeZone, StorePolls


class StoreReportTimeWindow():
    """
    process report time windows
    :param store_id:
    :return: total no of days, start local time, stop local time
    """
    async def main(self, store_id, window):
        start_local_time_windows = defaultdict(list)
        stop_local_time_windows = defaultdict(list)
        # time window in UTC
        start_utc, end_utc = await self.get_utc_window_bounds(window)

        # get timezone
        timezone = await self.get_store_timezone(store_id)

        # Convert UTC Start, End into local
        utc_into_local = lambda std_time, timezone: std_time.astimezone(pytz.timezone(timezone))
        # start_local, stop_local = utc_into_local(start_utc, timezone), utc_into_local(end_utc, timezone)
        start_local_time_windows[window].append(utc_into_local(start_utc, timezone))
        stop_local_time_windows[window].append(utc_into_local(end_utc, timezone))

        # get date/time range in days
        # total_days = (datetime.astimezone(stop_local)).day - (datetime.astimezone(start_local)).day
        # total_days += 1 if (window == "last_hour" or window == "last_day") else 6

        # return total_days, start_local_time_windows, stop_local_time_windows
        return {
            # "week_days": total_days,
            "start_time_local": start_local_time_windows,
            "stop_time_local": stop_local_time_windows
        }

    async def get_utc_window_bounds(self, time_window:str):
        """
        get time bound window in UTC
        :param time_window:
        :return: start, stop UTC
        """
        now_utc = datetime.now(timezone.utc) # Get the current UTC date and time

        if time_window == "last_hour":
            return (now_utc - timedelta(hours=1)), now_utc
        elif time_window == "last_day":
            return ((now_utc - timedelta(days=1)), (now_utc - timedelta(days=1))
                    .replace(hour=23, minute=59, second=59, microsecond=999999))
        else:
            # Calculate start of current week in UTC
            start_of_current_week_utc = now_utc - timedelta(days=now_utc.isoweekday() - 1)
            start_of_current_week_utc = start_of_current_week_utc.replace(hour=0, minute=0, second=0, microsecond=0)

            # Calculate start, end of last week in UTC
            start_of_last_week_utc = start_of_current_week_utc - timedelta(weeks=1)
            # add 6 more days to start of last week utc
            end_of_last_week_utc = start_of_last_week_utc + timedelta(days=6)
            end_of_last_week_utc = end_of_last_week_utc.replace(hour=23, minute=59, second=59, microsecond=999999)
            return start_of_last_week_utc, end_of_last_week_utc


    async def get_store_timezone(self, store_id) -> StoreTimeZone:
        """
        get timezone string from StoreTimeZone
        :param store_id:
        :return: timezone str
        """
        try:
            # return StoreTimeZone.filter(store_id=store_id).first().values("timezone_str")
            obj = await StoreTimeZone.filter(store_id=store_id).first()
            if obj: return obj.timezone_str
        except Exception as e:
            return None


class TimeWindowData(TypedDict):
    week_days: int
    start_time_local: Dict[str, List[str]]
    stop_time_local: Dict[str, List[str]]


class StoreBusinessAnalyzer:
    """
    Filter by business hours
    Filter Polls data
    Extrapolating uptime/downtime
    Interpolation of missing time blocks
    :param store_id, data: local time windows and total days
    :return:
    """
    async def main(self, store_id: str, data: TimeWindowData, window: str):
        full_day_window = lambda : None # store open 24*7
        # parse data
        start_time_local = data["start_time_local"]
        stop_time_local = data["stop_time_local"]
        # report_windows = start_time_local.keys() or stop_time_local.keys()

        # for window  in report_windows:
        total_days = 1 if window in ['last_hour', 'last_day'] else 6
        window_start_datetime_local = (start_time_local[window])[0]  # start time window
        window_stop_datetime_local = (stop_time_local[window])[0]  # stop time window
        final_prodctivity = defaultdict(list)

        # Filter by business hours in timezone windows
        # iterate in total days range
        total_uptime, total_downtime = 0, 0

        for day in range(total_days):
            day_lookup = window_start_datetime_local.weekday() or window_stop_datetime_local.weekday() if total_days == 1 else day
            business_hours = await self.filter_business_hours(store_id, day_lookup)
            if business_hours:
                business_hour_start_time_local, business_hour_stop_time_local = ([entry["start_time_local"]
                                                                                  for entry in business_hours],
                                                                                 [entry["end_time_local"]
                                                                                  for entry in business_hours])

                # Clip business hours to the requested window (window_start_datetime_local to window_stop_datetime_local)
                clipped_window_starts, clipped_window_ends = self.clip_business_hours_to_local_window(window_start_datetime_local,
                                                                                      window_stop_datetime_local,
                                                                                      business_hour_start_time_local,
                                                                                      business_hour_stop_time_local)

                if clipped_window_starts and clipped_window_ends:
                    if clipped_window_starts >= clipped_window_ends:
                        continue  # continue

                    # Filter Polls data in report_windows and total days
                    polls = await self.get_store_polls_status(store_id,
                                                              clipped_window_starts.astimezone(timezone.utc),
                                                              # UTC time for polls filter
                                                              clipped_window_ends.astimezone(
                                                                  timezone.utc))  # UTC time for polls filter
                    if polls is None:
                        total_uptime += (clipped_window_ends - clipped_window_starts).total_minutes()
                        continue
                    # Sort and interpolate
                    productivity_times = InterpolationWindow(
                        polls, clipped_window_starts, clipped_window_ends
                    )

                    total_window_uptime, total_window_downtime = productivity_times.work_flow()
                    # print(total_window_uptime, total_window_downtime)
                    total_uptime += total_window_uptime
                    total_downtime += total_window_downtime
                    final_prodctivity[window].append(
                        f"Up Time: {round(total_uptime / 60, 2)} Down Time: {round(total_downtime / 60, 2)}"
                    )
        return final_prodctivity

    def str_to_time(self, time_str: str, local_timezone) -> datetime.time:
        naive_dt = datetime.strptime(time_str, "%H:%M:%S")
        desired_timezone = pytz.timezone(local_timezone)
        return desired_timezone.localize(naive_dt)

    async def filter_business_hours(self,
                                    store_id: str,
                                    day: int
                                    ) -> StoreMenuHour:
        results = await StoreMenuHour.filter(
            Q(store_id=store_id) & Q(day_of_week=day)
        ).all().values('start_time_local', 'end_time_local', "day_of_week")
        return results

    def clip_business_hours_to_local_window(self,
                                                  window_start_datetime_local: str,
                                                  window_stop_datetime_local: str,
                                                  business_hour_start_time_local,
                                                  business_hour_stop_time_local):
        start_stop_local_tz = window_start_datetime_local.tzinfo and window_stop_datetime_local.tzinfo
        start_window_local_date = window_start_datetime_local.date()
        combined_window_starts_naive = datetime.strptime(
            f'{start_window_local_date} {business_hour_start_time_local[0]}', '%Y-%m-%d %H:%M:%S')
        window_starts = start_stop_local_tz.localize(
            combined_window_starts_naive) if not combined_window_starts_naive.tzinfo else combined_window_starts_naive.astimezone(
            start_stop_local_tz)

        stop_window_local_date = window_stop_datetime_local.date()
        combined_window_ends_naive = datetime.strptime(
            f'{stop_window_local_date} {business_hour_stop_time_local[0]}', '%Y-%m-%d %H:%M:%S')
        window_ends = start_stop_local_tz.localize(
            combined_window_ends_naive) if not combined_window_ends_naive.tzinfo else combined_window_ends_naive.astimezone(
            start_stop_local_tz)

        return window_starts, window_ends
        # window_starts = max(business_hour_start_time_local[0], window_start_datetime_local)
        # window_ends = max(business_hour_stop_time_local[0], window_stop_datetime_local)

    async def get_store_polls_status(self,
                                     store_id: str,
                                     window_start_time: Optional[datetime] = None,
                                     window_end_time: Optional[datetime] = None
                                     ) -> StorePolls:
        """
        filter store Active polls in UTC time
        :param store_id:
        :param window_start_time:
        :param window_end_time:
        :return: StorePolls
        """

        results = await (StorePolls.filter(
            Q(store_id=store_id) &
             # Q(status=True)) &
            (Q(timestamp_utc__gte=window_start_time) &
             Q(timestamp_utc__lte=window_end_time))
        ).values("store_id", "timestamp_utc", "status"))
        return results

        # results = await (StorePolls.filter(
        #     Q(store_id=store_id) &
        #     # Q(status=True)) &
        #     (Q(timestamp_utc__gte=window_start_time) &
        #      Q(timestamp_utc__lte=window_end_time))
        # ).annotate(active_polls=Case(
        #     When(status=True, then=F("timestamp_utc")),
        #     default=None
        # ),
        #     inactive_polls=Case(
        #         When(status=False, then=F("timestamp_utc")),
        #         default=None
        #     )).values('active_polls', 'inactive_polls'))
        # return results

class InterpolationWindow:
    """
    Interpolation Workflow
    calculate window uptime, downtime:
    Polls coverage base:
        Polls exist but miss start of day: downtime until first poll
        Polls miss end of day: downtime after last poll until window_downtime
        Status spans multiple days	Don't carry over — each day is treated independently
        No polls at all	Assume 100% uptime
    """
    def __init__(self, polls, window_start: datetime, window_end: datetime):
        self.polls = polls
        self.window_start = window_start
        self.window_end = window_end

    def work_flow(self):
        # Todo: add 100% uptime if polls None
        df = pd.DataFrame(self.polls)

        local_tz = self.window_start.tzinfo or self.window_end.tzinfo
        if 'timestamp_utc' in df.columns:
            df.rename(columns={'timestamp_utc': 'timestamp'}, inplace=True)

            df["timestamp"] = df['timestamp'].dt.tz_convert(local_tz) # convert to local timezone
            df = df.sort_values(by='timestamp', ascending=True) # sort by local timestamp
            df = df[(df['timestamp'] >= self.window_start) & (df['timestamp'] <= self.window_end)] # confirm filter range to search

        intervals = []
        prev_time = self.window_start
        prev_status = True # inactive

        for _, row in df.iterrows():
            current_time = row['timestamp']
            duration = (current_time - prev_time).total_seconds() / 60  # in minutes
            intervals.append((duration, prev_status))
            prev_time = current_time
            prev_status = row['status']

        if prev_time < self.window_end:
            duration = (self.window_end - prev_time).total_seconds() / 60
            intervals.append((duration, prev_status))

        uptime = sum(d for d, s in intervals if s)
        downtime = sum(d for d, s in intervals if not s)

        return uptime, downtime

