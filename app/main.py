#!/usr/bin/env python3
#########################################################################################################################################################################
#
# Created by: Jan Hüls "finex7070" StickyStoneStudio GmbH
#
# Script: main.py
#
# Description:
# - Automatic import Public Holidays and Absences into CalDAV calender
# - Built-in `/metrics` endpoint for Prometheus / Grafana monitoring
# - Dockerized for fast, reproducible deployment
#
# Notes:
# - Expects environment variables for API keys and configuration.
#
# License:
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#
#########################################################################################################################################################################

import os, httpx, icalendar, caldav
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, date, timedelta, timezone
from fastapi import FastAPI, Response
from contextlib import asynccontextmanager
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from prometheus_client import Gauge, Counter, generate_latest, CONTENT_TYPE_LATEST

# --- Environment Variables ---
load_dotenv()

def get_env_bool(var_name, default=False) -> bool:
    val = os.getenv(var_name, str(default)).lower()
    
    return val in ('true', '1', 't', 'y', 'yes')

KIMAI_API_URL = os.getenv("KIMAI_API_URL")
KIMAI_API_KEY = os.getenv("KIMAI_API_KEY")
CALDAV_URL = os.getenv("CALDAV_URL")
CALDAV_USERNAME = os.getenv("CALDAV_USERNAME", None)
CALDAV_PASSWORD = os.getenv("CALDAV_PASSWORD", None)
SKIP_VERIFY_CERTIFICATE = get_env_bool("SKIP_VERIFY_CERTIFICATE", False)

REQUIRED_ENV_VARS = {
    "KIMAI_API_URL": KIMAI_API_URL,
    "KIMAI_API_KEY": KIMAI_API_KEY,
    "CALDAV_URL": CALDAV_URL
}

missing = [k for k, v in REQUIRED_ENV_VARS.items() if not v]

if missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

# --- Constants ---
PUBLIC_HOLIDAY_PREFIX = "kimai-public_holiday-"
ABSENCE_PREFIX = "kimai-absence-"

# --- FastAPI & Scheduler ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(cronjob, 'interval', minutes=10, id="cronjob", next_run_time=datetime.now())
    scheduler.start()
    yield
    scheduler.shutdown()

scheduler = AsyncIOScheduler()
app = FastAPI(lifespan=lifespan)

async def cronjob():
    await sync_public_holidays()
    await sync_absences()

# --- Metrics ---
METRIC_PUBLIC_HOLIDAYS = Gauge(
    'public_holidays_total', 
    'Number of public holidays currently synced'
)

METRIC_ABSENCES = Gauge(
    'absences_total', 
    'Number of absences currently synced'
)

METRIC_ERRORS = Counter(
    'sync_errors_total', 
    'Total number of errors encountered during sync'
)

# --- Kimai Models ---
class PublicHoliday(BaseModel):
    id: Optional[int] = None
    date: str
    name: str
    publicHolidayGroup: Optional[PublicHolidayGroup] = None
    halfDay: Optional[bool] = None

class PublicHolidayGroup(BaseModel):
    id: Optional[int] = None
    name: str

class Absence(BaseModel):
    id: Optional[int] = None
    user: User
    date: str
    duration: Optional[int] = None
    type: Optional[str] = None
    status: Optional[str] = None
    halfDay: Optional[bool] = None

class User(BaseModel):
    apiToken: Optional[bool] = None
    locale: Optional[str] = None
    timezone: Optional[str] = None
    language: Optional[str] = None
    initials: Optional[str] = None
    color_safe: Optional[str] = None
    id: Optional[int] = None
    alias: Optional[str] = None
    title: Optional[str] = None
    avatar: Optional[str] = None
    username: str
    email: str
    accountNumber: Optional[str] = None
    enabled: Optional[bool] = None
    systemAccount: Optional[bool] = None
    color: Optional[str] = None

# --- Kimai API Functions ---
async def get_public_holidays(group: Optional[int] = None, begin: Optional[datetime] = None, end: Optional[datetime] = None) -> List[PublicHoliday]:
    headers = {
        "Authorization": f"Bearer {KIMAI_API_KEY}",
        "Content-Type": "application/json"
    }
    params = {}

    if begin:
        params["begin"] = begin.isoformat()

    if end:
        params["end"] = end.isoformat()

    if group is not None:
        params["group"] = group

    async with httpx.AsyncClient(verify=not SKIP_VERIFY_CERTIFICATE) as client:
        response = await client.get(f"{KIMAI_API_URL}/public-holidays", headers=headers, params=params)
        response.raise_for_status()
        holidays_data = response.json()
        holidays = [PublicHoliday(**holiday) for holiday in holidays_data]

        return holidays
    
async def get_absences(user: Optional[int] = None, begin: Optional[datetime] = None, end: Optional[datetime] = None) -> List[Absence]:
    headers = {
        "Authorization": f"Bearer {KIMAI_API_KEY}",
        "Content-Type": "application/json"
    }
    params = {}

    if begin:
        params["begin"] = begin.isoformat()

    if end:
        params["end"] = end.isoformat()

    if user is not None:
        params["user"] = user

    async with httpx.AsyncClient(verify=not SKIP_VERIFY_CERTIFICATE) as client:
        response = await client.get(f"{KIMAI_API_URL}/absences", headers=headers, params=params)
        response.raise_for_status()
        absences_data = response.json()
        absences = [Absence(**absence) for absence in absences_data]

        return absences
    
async def get_users() -> List[User]:
    headers = {
        "Authorization": f"Bearer {KIMAI_API_KEY}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient(verify=not SKIP_VERIFY_CERTIFICATE) as client:
        response = await client.get(f"{KIMAI_API_URL}/users", headers=headers)
        response.raise_for_status()
        users_data = response.json()
        users = [User(**user) for user in users_data]

        return users
    
# --- CalDAV Functions ---
async def get_calendar():
    if CALDAV_USERNAME and CALDAV_PASSWORD:
        client = caldav.DAVClient(url=CALDAV_URL, username=CALDAV_USERNAME, password=CALDAV_PASSWORD, ssl_verify_cert=not SKIP_VERIFY_CERTIFICATE)
    else:
        client = caldav.DAVClient(url=CALDAV_URL, ssl_verify_cert=not SKIP_VERIFY_CERTIFICATE)

    return client.calendar(url=CALDAV_URL)

async def get_event_uids(prefix: str, start: datetime, end: datetime) -> List[str]:
    uids = []

    try:
        calendar = await get_calendar()
        events = calendar.date_search(start=start, end=end)

        for event in events:
            try:
                uid = None
                ical = icalendar.Calendar.from_ical(event.data)

                for component in ical.walk():
                    if component.name == "VEVENT":
                        uid = str(component.get('uid'))
                        break

                if uid and uid.startswith(prefix):
                    uids.append(uid)
            except Exception:
                continue
    except Exception as e:
        print(f"Error fetching event uids for prefix {prefix}: {e}")
        METRIC_ERRORS.inc()

    return uids
    
async def put_events(events: List[icalendar.Event]):
    if not events:
        return
    
    try:
        calendar = await get_calendar()

        for event in events:
            cal = icalendar.Calendar()
            cal.add('prodid', '-//Kimai CalDAV Bridge//EN')
            cal.add('version', '2.0')
            cal.add_component(event)
            calendar.add_event(cal.to_ical())
    except Exception as e:
        print(f"Error putting events in CalDAV: {e}")
        METRIC_ERRORS.inc()

async def delete_events(uids: List[str]):
    if not uids:
        return
    try:
        calendar = await get_calendar()

        for uid in uids:
            results = calendar.event_by_uid(uid)

            if results:
                results.delete()
    except Exception as e:
        print(f"Error deleting events in CalDAV: {e}")
        METRIC_ERRORS.inc()

# --- Sync Functions ---
async def sync_public_holidays():
    try:
        today = date.today()
        current_year = today.year
        start_search = datetime(current_year - 1, 1, 1)
        end_search = datetime(current_year + 1, 12, 31, 23, 59, 59)
        holidays = []
        group = 1
        empty = 0

        while empty < 10:
            try:
                group_holidays = await get_public_holidays(group, start_search, end_search)

                if group_holidays:
                    holidays.extend(group_holidays)
                    empty = 0
                else:
                    empty += 1
            except Exception:
                empty += 1

            group += 1

        existing_uids = await get_event_uids(PUBLIC_HOLIDAY_PREFIX, start_search, end_search)
        kimai_uids = set()
        events_to_put = []

        for holiday in holidays:
            uid = f"{PUBLIC_HOLIDAY_PREFIX}{holiday.id}"
            kimai_uids.add(uid)

            if 'T' in holiday.date:
                dt = datetime.fromisoformat(holiday.date)
                dtstart = dt.date()
            else:
                dtstart = date.fromisoformat(holiday.date)

            summary = holiday.name
            categories = []

            if holiday.halfDay:
                summary += " (Half day)"

            if holiday.publicHolidayGroup:
                categories = ['Kimai', 'Public holiday', holiday.publicHolidayGroup.name]
                summary += f" ({holiday.publicHolidayGroup.name})"
            else:
                categories = ['Kimai', 'Public holiday']

            event = icalendar.Event()
            event.add('uid', uid)
            event.add('dtstamp', datetime.now(timezone.utc))
            event.add('dtstart', dtstart)
            event.add('dtend', dtstart + timedelta(days=1))
            event.add('summary', summary)
            event.add('categories', categories)
            event.add('transp', 'TRANSPARENT')
            events_to_put.append(event)

        uids_to_delete = [uid for uid in existing_uids if uid not in kimai_uids]

        if uids_to_delete:
            await delete_events(uids_to_delete)

        if events_to_put:
            await put_events(events_to_put)

        METRIC_PUBLIC_HOLIDAYS.set(len(events_to_put))
    except Exception as e:
        print(f"Error syncing public holidays: {e}")
        METRIC_ERRORS.inc()

async def sync_absences():
    try:
        today = date.today()
        current_year = today.year
        start_search = datetime(current_year - 1, 1, 1)
        end_search = datetime(current_year + 1, 12, 31, 23, 59, 59)
        users = await get_users()
        absences = []

        for user in users:
            try:
                user_absences = await get_absences(user.id, start_search, end_search)
                absences.extend(user_absences)
            except Exception:
                continue

        existing_uids = await get_event_uids(ABSENCE_PREFIX, start_search, end_search)
        kimai_uids = set()
        events_to_put = []

        for absence in absences:
            uid = f"{ABSENCE_PREFIX}{absence.id}"
            kimai_uids.add(uid)
            
            if 'T' in absence.date:
                dt = datetime.fromisoformat(absence.date)
                dtstart = dt.date()
            else:
                dtstart = date.fromisoformat(absence.date)

            user = absence.user.alias if absence.user.alias else absence.user.username
            summary = f"{absence.type.capitalize()} - {user}"

            if absence.halfDay:
                summary += " (Half day)"
            elif absence.duration:
                hours = absence.duration / 3600
                
                if hours < 8:
                    summary += f" ({hours:g}h)"

            event = icalendar.Event()
            event.add('uid', uid)
            event.add('dtstamp', datetime.now(timezone.utc))
            event.add('dtstart', dtstart)
            event.add('dtend', dtstart + timedelta(days=1))
            event.add('summary', summary)
            event.add('categories', ['Kimai', 'Absence', absence.type.capitalize()])
            events_to_put.append(event)

        uids_to_delete = [uid for uid in existing_uids if uid not in kimai_uids]

        if uids_to_delete:
            await delete_events(uids_to_delete)

        if events_to_put:
            await put_events(events_to_put)

        METRIC_ABSENCES.set(len(events_to_put))
    except Exception as e:
        print(f"Error syncing absences: {e}")
        METRIC_ERRORS.inc()

# --- FastAPI Endpoints ---
@app.get("/healthz")
async def healthz_endpoint():
    return {"status": "running"}

@app.get("/metrics")
async def metrics_endpoint():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)