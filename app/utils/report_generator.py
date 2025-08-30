from collections import defaultdict
from configparser import Interpolation
from datetime import datetime, timedelta, timezone, tzinfo
from typing import TypedDict, Dict, List, Optional

import pytz
from tortoise.expressions import Q

from app.models.business_menu import StoreMenuHour
from app.models.stores import StoreTimeZone, StorePolls


class StoreReportTimeWindow():
    """
    process report time windows
    :param store_id:
    :return: total no of days, start local time, stop local time
    """
    async def main(self, store_id):
        # store_id = "652917e6-645f-4af4-b52e-13ce1bccdbc9"

        start_local_time_windows = defaultdict(list)
        stop_local_time_windows = defaultdict(list)
        for window in ["last_hour", "last_day", "last_week"]:
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
    Interpolation of missing time blocks
    Extrapolating uptime/downtime
    :param store_id, data: local time windows and total days
    :return:
    """
    async def main(self, store_id: str, data: TimeWindowData):
        full_day_window = lambda : None # store open 24*7
        # parse data
        total_days = 6

        start_time_local = data["start_time_local"]
        stop_time_local = data["stop_time_local"]
        report_windows = start_time_local.keys() or stop_time_local.keys()

        for window  in report_windows:
            window_start_time_local = (start_time_local[window])[0] # start time window
            window_stop_time_local = (stop_time_local[window])[0] #stop time window
            # get window timezone
            local_timezone = window_start_time_local.tzinfo and window_stop_time_local.tzinfo

            # Filter by business hours in reporting windows
            # iterate in total days range
            # calculate total_uptime, total_downtime
            total_uptime, total_downtime = 0, 0
            for day in range(total_days):
                business_hours = await self.filter_business_hours(store_id, day)
                if business_hours:
                    business_hour_start_time_local, business_hour_stop_time_local = ([self.str_to_time(entry["start_time_local"])
                                                                                      for entry in business_hours],
                                                                                     [self.str_to_time(entry["end_time_local"])
                                                                                      for entry in business_hours])

                    # Clip business hours to the requested window (window_start_time_local to window_stop_time_local)
                    window_starts = max(business_hour_start_time_local[0].replace(tzinfo=local_timezone), window_start_time_local)
                    window_ends = max(business_hour_stop_time_local[0].replace(tzinfo=local_timezone), window_stop_time_local)

                    if window_starts and window_ends:
                        if window_starts >= window_ends:
                            continue # continue

                        # Filter Polls data in report_windows and total days
                        # only Active
                        polls = await self.get_store_polls_status(store_id,
                                                                  window_starts.astimezone(timezone.utc), # UTC time for polls filter
                                                                  window_ends.astimezone(timezone.utc)) # UTC time for polls filter

                        if polls is None:
                            # Todo: add 100% uptime
                            total_uptime += (window_ends - window_starts) # 100% uptime
                            continue

                        print(polls)
                        # Sort and interpolate
                        window_uptime = InterpolationWindow(
                            polls, window_starts, window_ends
                        )

    def str_to_time(self, time_str: str) -> datetime.time:
        return datetime.strptime(time_str, "%H:%M:%S")

    async def filter_business_hours(self,
                                    store_id: str,
                                    day: int
                                    ) -> StoreMenuHour:
        results = await StoreMenuHour.filter(
            Q(store_id=store_id) & Q(day_of_week=day)
        ).all().values('start_time_local', 'end_time_local', "day_of_week")
        return results

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
        print(f"{window_start_time}------{window_end_time}")
        results = await (StorePolls.filter(
            (Q(store_id=store_id) &
             Q(status=True)) &
            (Q(timestamp_utc__gte=window_start_time) &
             Q(timestamp_utc__lte=window_end_time))
        ).values("timestamp_utc", "store_id"))
        return results

class InterpolationWindow:
    """
    Interpolation Workflow
    calculate window uptime, downtime:
    Polls coverage base:
        Polls exist but miss start of day: downtime until first poll
        Polls miss end of day: downtime after last poll until window_downtime
        No polls at all	Assume 100% uptime
        Status spans multiple days	Don't carry over — each day is treated independently
    """
    def __init__(self, polls, window_start, window_end):
        self.polls = polls
        self.window_start = window_start
        self.window_end = window_end

        # return: total uptime & downtime
        self.global_uptime, self.global_downtime = 0, 0
        self.work_flow()

    def work_flow(self):
        pass
        # before 1st poll of the day

        # between window time polls

        # after last poll of the day

